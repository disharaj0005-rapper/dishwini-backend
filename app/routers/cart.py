from fastapi import APIRouter, Depends, HTTPException, status
from app.dependencies import get_current_user
from app.database import get_db
from app.schemas.cart import CartAddRequest, CartResponse, CartItemResponse
from supabase import Client

router = APIRouter()


@router.get("", response_model=CartResponse)
async def get_cart(
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db)
):
    """Get the current user's cart."""
    user_id = current_user["id"]

    cart_items_res = db.table("cart_items").select("*").eq("user_id", user_id).execute()
    cart_items_data = cart_items_res.data
    
    if not cart_items_data:
        return CartResponse(items=[], total=0.0, item_count=0)

    # 1. Fetch all variants in bulk
    variant_ids = [item["product_variant_id"] for item in cart_items_data]
    variants_res = db.table("product_variants").select("*").in_("id", variant_ids).execute()
    variants_map = {v["id"]: v for v in variants_res.data}

    # 2. Fetch all products in bulk
    product_ids = list(set(v["product_id"] for v in variants_res.data))
    products_res = db.table("products").select("id, name, slug, price").in_("id", product_ids).execute()
    products_map = {p["id"]: p for p in products_res.data}

    # 3. Fetch all images for these products (to pick the first one)
    images_res = db.table("product_images").select("product_id, image_url").in_("product_id", product_ids).order("display_order").execute()
    # Create a map for the first image of each product
    images_map = {}
    for img in images_res.data:
        if img["product_id"] not in images_map:
            images_map[img["product_id"]] = img["image_url"]

    items = []
    total = 0.0

    for item in cart_items_data:
        v = variants_map.get(item["product_variant_id"])
        if not v:
            continue

        p = products_map.get(v["product_id"])
        if not p:
            continue

        price = v.get("price_override") or p["price"]
        image_url = images_map.get(p["id"])

        cart_item = CartItemResponse(
            id=item["id"],
            product_variant_id=item["product_variant_id"],
            quantity=item["quantity"],
            product_name=p["name"],
            product_slug=p["slug"],
            size=v.get("size"),
            color=v.get("color"),
            price=price,
            image_url=image_url,
            stock=v.get("stock", 0)
        )
        items.append(cart_item)
        total += price * item["quantity"]

    return CartResponse(
        items=items,
        total=round(total, 2),
        item_count=len(items)
    )


@router.post("/add")
async def add_to_cart(
    request: CartAddRequest,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db)
):
    """Add an item to cart."""
    user_id = current_user["id"]

    # Verify variant exists and has stock
    variant = db.table("product_variants").select("*").eq(
        "id", request.product_variant_id
    ).execute()

    if not variant.data:
        raise HTTPException(status_code=404, detail="Product variant not found")

    if variant.data[0]["stock"] < request.quantity:
        raise HTTPException(status_code=400, detail="Insufficient stock")

    # Check if already in cart
    existing = db.table("cart_items").select("*").eq(
        "user_id", user_id
    ).eq("product_variant_id", request.product_variant_id).execute()

    if existing.data:
        new_qty = existing.data[0]["quantity"] + request.quantity
        if new_qty > variant.data[0]["stock"]:
            raise HTTPException(status_code=400, detail="Insufficient stock")
        db.table("cart_items").update(
            {"quantity": new_qty}
        ).eq("id", existing.data[0]["id"]).execute()
    else:
        db.table("cart_items").insert({
            "user_id": user_id,
            "product_variant_id": request.product_variant_id,
            "quantity": request.quantity
        }).execute()

    return {"message": "Item added to cart"}


@router.put("/{item_id}")
async def update_cart_item(
    item_id: str,
    request: CartAddRequest,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db)
):
    """Update cart item quantity."""
    user_id = current_user["id"]

    existing = db.table("cart_items").select("*").eq(
        "id", item_id
    ).eq("user_id", user_id).execute()

    if not existing.data:
        raise HTTPException(status_code=404, detail="Cart item not found")

    if request.quantity <= 0:
        db.table("cart_items").delete().eq("id", item_id).execute()
        return {"message": "Item removed from cart"}

    # Check stock
    variant = db.table("product_variants").select("stock").eq(
        "id", existing.data[0]["product_variant_id"]
    ).execute()

    if variant.data and request.quantity > variant.data[0]["stock"]:
        raise HTTPException(status_code=400, detail="Insufficient stock")

    db.table("cart_items").update(
        {"quantity": request.quantity}
    ).eq("id", item_id).execute()

    return {"message": "Cart updated"}


@router.delete("/remove/{item_id}")
async def remove_from_cart(
    item_id: str,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db)
):
    """Remove an item from cart."""
    user_id = current_user["id"]

    db.table("cart_items").delete().eq(
        "id", item_id
    ).eq("user_id", user_id).execute()

    return {"message": "Item removed from cart"}


@router.delete("/clear")
async def clear_cart(
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db)
):
    """Clear all items from cart."""
    db.table("cart_items").delete().eq("user_id", current_user["id"]).execute()
    return {"message": "Cart cleared"}
