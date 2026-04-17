from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
from app.dependencies import get_current_user, require_admin
from app.database import get_db
from app.schemas.order import (
    OrderCreateRequest, OrderUpdateRequest,
    OrderResponse, OrderListResponse
)
from app.services.mail_service import send_order_confirmation
from supabase import Client

router = APIRouter()


@router.post("/create", response_model=OrderResponse, status_code=201)
async def create_order(
    request: OrderCreateRequest,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db)
):
    """Create an order from the user's cart."""
    user_id = current_user["id"]

    # Get cart items
    cart = db.table("cart_items").select("*").eq("user_id", user_id).execute()
    if not cart.data:
        raise HTTPException(status_code=400, detail="Cart is empty")

    # Build shipping address
    shipping_address = None
    if request.shipping_address:
        shipping_address = request.shipping_address.model_dump()
    elif request.address_id:
        addr = db.table("addresses").select("*").eq("id", request.address_id).execute()
        if addr.data:
            shipping_address = addr.data[0]
    
    if not shipping_address:
        raise HTTPException(status_code=400, detail="Shipping address required")

    # Calculate total
    total = 0.0
    order_items_data = []

    for item in cart.data:
        variant = db.table("product_variants").select("*").eq(
            "id", item["product_variant_id"]
        ).execute()

        if not variant.data:
            continue

        v = variant.data[0]
        product = db.table("products").select("*").eq("id", v["product_id"]).execute()
        if not product.data:
            continue

        p = product.data[0]
        price = v.get("price_override") or p["price"]

        # Check stock
        if v["stock"] < item["quantity"]:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for {p['name']}"
            )

        # Get product image
        image = db.table("product_images").select("image_url").eq(
            "product_id", p["id"]
        ).order("display_order").limit(1).execute()

        variant_info = " / ".join(filter(None, [v.get("size"), v.get("color")]))

        order_items_data.append({
            "product_variant_id": item["product_variant_id"],
            "product_name": p["name"],
            "variant_info": variant_info,
            "quantity": item["quantity"],
            "price": price,
            "image_url": image.data[0]["image_url"] if image.data else None
        })

        total += price * item["quantity"]

    # Apply coupon if provided
    discount = 0.0
    coupon_id = None
    if request.coupon_code:
        coupon = db.table("coupons").select("*").eq(
            "code", request.coupon_code
        ).eq("is_active", True).execute()

        if not coupon.data:
            raise HTTPException(status_code=400, detail="Invalid or inactive coupon code")

        c = coupon.data[0]

        # Validate coupon expiry
        if c.get("expires_at"):
            from datetime import datetime, timezone
            expires_at = datetime.fromisoformat(c["expires_at"].replace("Z", "+00:00"))
            if datetime.now(timezone.utc) > expires_at:
                raise HTTPException(status_code=400, detail="This coupon has expired")

        # Validate usage limit
        if c.get("usage_limit") is not None and (c.get("used_count", 0) >= c["usage_limit"]):
            raise HTTPException(status_code=400, detail="This coupon has reached its usage limit")

        # Validate minimum order amount
        if c.get("min_order_amount") and total < float(c["min_order_amount"]):
            raise HTTPException(
                status_code=400,
                detail=f"Minimum order amount for this coupon is ₹{c['min_order_amount']}"
            )

        discount = total * (float(c["discount_percentage"]) / 100)
        if c.get("max_discount_amount") and discount > float(c["max_discount_amount"]):
            discount = float(c["max_discount_amount"])
        coupon_id = c["id"]

        # Increment used_count
        db.table("coupons").update({
            "used_count": (c.get("used_count", 0) or 0) + 1
        }).eq("id", c["id"]).execute()

    # Create order
    is_cod = request.payment_method == "cod"
    
    order_data = {
        "user_id": user_id,
        "total_amount": round(total - discount, 2),
        "shipping_amount": 0,
        "discount_amount": round(discount, 2),
        "shipping_address": shipping_address,
        "coupon_id": coupon_id,
        "notes": request.notes,
        "payment_method": request.payment_method,
        "payment_status": "pending",
        "status": "confirmed" if is_cod else "pending"
    }

    order_result = db.table("orders").insert(order_data).execute()
    order = order_result.data[0]

    # Create order items in bulk
    for item_data in order_items_data:
        item_data["order_id"] = order["id"]
    
    if order_items_data:
        db.table("order_items").insert(order_items_data).execute()

    # Update stock
    for item in cart.data:
        variant = db.table("product_variants").select("stock").eq(
            "id", item["product_variant_id"]
        ).execute()
        if variant.data:
            new_stock = variant.data[0]["stock"] - item["quantity"]
            db.table("product_variants").update(
                {"stock": new_stock}
            ).eq("id", item["product_variant_id"]).execute()

    # Clear cart
    db.table("cart_items").delete().eq("user_id", user_id).execute()

    # Fetch complete order
    return await get_order(order["id"], current_user, db)


@router.get("", response_model=OrderListResponse)
async def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db)
):
    """List orders. Admins see all orders, customers see only their own."""
    query = db.table("orders").select("*", count="exact")

    if current_user["role"] != "admin":
        query = query.eq("user_id", current_user["id"])

    if status_filter:
        query = query.eq("status", status_filter)

    offset = (page - 1) * page_size
    result = query.order("created_at", desc=True).range(offset, offset + page_size - 1).execute()

    if not result.data:
        return OrderListResponse(orders=[], total=result.count or 0)

    # Fetch all items for these orders in one query
    order_ids = [o["id"] for o in result.data]
    items_res = db.table("order_items").select("*").in_("order_id", order_ids).execute()
    
    # Group items by order_id
    items_by_order = {}
    for item in items_res.data:
        oid = item["order_id"]
        if oid not in items_by_order:
            items_by_order[oid] = []
        items_by_order[oid].append(item)

    orders = []
    for order in result.data:
        order["items"] = items_by_order.get(order["id"], [])
        orders.append(order)

    return OrderListResponse(
        orders=orders,
        total=result.count or 0
    )


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db)
):
    """Get a single order."""
    query = db.table("orders").select("*").eq("id", order_id)

    if current_user["role"] != "admin":
        query = query.eq("user_id", current_user["id"])

    result = query.execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Order not found")

    order = result.data[0]
    items = db.table("order_items").select("*").eq("order_id", order["id"]).execute()
    order["items"] = items.data

    return order


@router.put("/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(
    order_id: str,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db)
):
    """Cancel an order (customer only)."""
    # Fetch order
    query = db.table("orders").select("*").eq("id", order_id)
    if current_user["role"] != "admin":
        query = query.eq("user_id", current_user["id"])
    
    result = query.execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Order not found")
        
    order = result.data[0]
    
    # Check if cancellable
    if order["status"] not in ["pending", "confirmed"]:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot cancel order in {order['status']} status"
        )
        
    # Update order status
    db.table("orders").update({"status": "cancelled"}).eq("id", order_id).execute()
    
    # Restore inventory
    items = db.table("order_items").select("*").eq("order_id", order_id).execute()
    for item in items.data:
        variant = db.table("product_variants").select("stock").eq("id", item["product_variant_id"]).execute()
        if variant.data:
            current_stock = variant.data[0]["stock"]
            db.table("product_variants").update({
                "stock": current_stock + item["quantity"]
            }).eq("id", item["product_variant_id"]).execute()
            
    return await get_order(order_id, current_user, db)


@router.put("/{order_id}", response_model=OrderResponse)
async def update_order(
    order_id: str,
    request: OrderUpdateRequest,
    admin: dict = Depends(require_admin),
    db: Client = Depends(get_db)
):
    """Update order status (admin only)."""
    existing = db.table("orders").select("*").eq("id", order_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Order not found")

    order = existing.data[0]
    update_data = request.model_dump(exclude_unset=True)

    # Only allow manual payment_status changes for COD orders
    if "payment_status" in update_data:
        allowed_statuses = ["pending", "paid", "refunded"]
        if update_data["payment_status"] not in allowed_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid payment status. Allowed: {', '.join(allowed_statuses)}"
            )

    # Inventory handling when manually changing status to 'cancelled'
    if update_data.get("status") == "cancelled" and order["status"] != "cancelled":
        items = db.table("order_items").select("*").eq("order_id", order_id).execute()
        for item in items.data:
            variant = db.table("product_variants").select("stock").eq("id", item["product_variant_id"]).execute()
            if variant.data:
                current_stock = variant.data[0]["stock"]
                db.table("product_variants").update({
                    "stock": current_stock + item["quantity"]
                }).eq("id", item["product_variant_id"]).execute()

    db.table("orders").update(update_data).eq("id", order_id).execute()

    return await get_order(order_id, admin, db)
