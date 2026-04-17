from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
from app.dependencies import get_current_user, require_admin
from app.database import get_db
from app.schemas.user import (
    UserProfileResponse, UserUpdateRequest,
    AddressResponse, AddressCreateRequest
)
from supabase import Client

router = APIRouter()


@router.get("/profile", response_model=UserProfileResponse)
async def get_profile(current_user: dict = Depends(get_current_user)):
    """Get current user's profile."""
    return current_user


@router.put("/profile", response_model=UserProfileResponse)
async def update_profile(
    request: UserUpdateRequest,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db)
):
    """Update current user's profile."""
    update_data = request.model_dump(exclude_unset=True)
    if not update_data:
        return current_user

    result = db.table("users").update(update_data).eq("id", current_user["id"]).execute()
    if not result.data:
        return current_user
    return result.data[0]


@router.get("/addresses")
async def get_addresses(
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db)
):
    """Get user's saved addresses."""
    result = db.table("addresses").select("*").eq(
        "user_id", current_user["id"]
    ).order("is_default", desc=True).execute()
    return result.data


@router.post("/addresses", status_code=201)
async def create_address(
    request: AddressCreateRequest,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db)
):
    """Add a new address."""
    address_data = request.model_dump()
    address_data["user_id"] = current_user["id"]

    # If this is the default address, unset other defaults
    if request.is_default:
        db.table("addresses").update(
            {"is_default": False}
        ).eq("user_id", current_user["id"]).execute()

    result = db.table("addresses").insert(address_data).execute()
    return result.data[0]


@router.delete("/addresses/{address_id}")
async def delete_address(
    address_id: str,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db)
):
    """Delete an address."""
    db.table("addresses").delete().eq(
        "id", address_id
    ).eq("user_id", current_user["id"]).execute()
    return {"message": "Address deleted"}


# =====================
# Admin endpoints
# =====================

@router.get("/customers")
async def list_customers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    admin: dict = Depends(require_admin),
    db: Client = Depends(get_db)
):
    """List all customers (admin only)."""
    query = db.table("users").select("*", count="exact").eq("role", "customer")

    if search:
        query = query.or_(f"email.ilike.%{search}%,full_name.ilike.%{search}%")

    offset = (page - 1) * page_size
    result = query.order("created_at", desc=True).range(offset, offset + page_size - 1).execute()

    # Get order count for each customer
    customers = list(result.data)
    user_ids = [user["id"] for user in customers]
    
    if user_ids:
        orders_res = db.table("orders").select("user_id").in_("user_id", user_ids).execute()
        order_counts = {}
        for order in orders_res.data:
            uid = order["user_id"]
            order_counts[uid] = order_counts.get(uid, 0) + 1
            
        for user in customers:
            user["order_count"] = order_counts.get(user["id"], 0)
    else:
        for user in customers:
            user["order_count"] = 0

    return {
        "customers": customers,
        "total": result.count or 0,
        "page": page,
        "page_size": page_size
    }


@router.get("/stats")
async def get_admin_stats(
    admin: dict = Depends(require_admin),
    db: Client = Depends(get_db)
):
    """Get dashboard statistics (admin only)."""
    total_orders = db.table("orders").select("id", count="exact").execute()
    total_customers = db.table("users").select("id", count="exact").eq("role", "customer").execute()
    total_products = db.table("products").select("id", count="exact").execute()

    # Revenue
    paid_orders = db.table("orders").select("total_amount").eq("payment_status", "paid").execute()
    total_revenue = sum(o["total_amount"] for o in paid_orders.data) if paid_orders.data else 0

    # Recent orders
    recent_orders = db.table("orders").select("*").order(
        "created_at", desc=True
    ).limit(5).execute()

    return {
        "total_orders": total_orders.count or 0,
        "total_customers": total_customers.count or 0,
        "total_products": total_products.count or 0,
        "total_revenue": round(total_revenue, 2),
        "recent_orders": recent_orders.data
    }
