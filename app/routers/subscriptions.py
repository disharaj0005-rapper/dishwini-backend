from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from app.dependencies import require_admin
from app.database import get_db
from supabase import Client

router = APIRouter()

class SubscriptionRequest(BaseModel):
    email: EmailStr

@router.post("", status_code=status.HTTP_201_CREATED)
async def subscribe_newsletter(
    request: SubscriptionRequest,
    db: Client = Depends(get_db)
):
    """Subscribe to the newsletter."""
    # Check if existing
    existing = db.table("newsletter_subscriptions").select("*").eq("email", request.email).execute()
    if existing.data:
        return {"message": "Already subscribed", "data": existing.data[0]}
        
    subscription_data = {"email": request.email, "is_active": True}
    
    try:
        result = db.table("newsletter_subscriptions").insert(subscription_data).execute()
        return {"message": "Subscribed successfully", "data": result.data[0]}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to subscribe: {str(e)}"
        )

@router.get("")
async def get_subscriptions(
    admin: dict = Depends(require_admin),
    db: Client = Depends(get_db)
):
    """Get all subscriptions (admin only)."""
    result = db.table("newsletter_subscriptions").select("*").order("created_at", desc=True).execute()
    return result.data
