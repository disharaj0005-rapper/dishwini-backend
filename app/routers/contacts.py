from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from app.dependencies import require_admin
from app.database import get_db
from supabase import Client

router = APIRouter()

class ContactRequest(BaseModel):
    name: str
    email: EmailStr
    subject: str = None
    message: str

from app.services.mail_service import send_email
from app.config import get_settings

settings = get_settings()

@router.post("", status_code=status.HTTP_201_CREATED)
async def submit_contact(
    request: ContactRequest,
    db: Client = Depends(get_db)
):
    """Submit a contact message."""
    contact_data = request.model_dump()
    
    try:
        result = db.table("contact_messages").insert(contact_data).execute()
        
        # Send EmailJS Notification
        if settings.EMAILJS_SERVICE_ID and settings.EMAILJS_CONTACT_TEMPLATE_ID:
            template_params = {
                "name": request.name,
                "email": request.email,
                "subject": request.subject or "No Subject",
                "message": request.message
            }
            # We don't await blocking error if email fails, but since it's an await call we must await it.
            try:
                await send_email(settings.EMAILJS_CONTACT_TEMPLATE_ID, template_params)
            except Exception as e:
                print(f"Failed to send contact notification email: {e}")

        return {"message": "Contact message submitted successfully", "data": result.data[0]}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit message: {str(e)}"
        )

@router.get("")
async def get_contacts(
    admin: dict = Depends(require_admin),
    db: Client = Depends(get_db)
):
    """Get all contact messages."""
    result = db.table("contact_messages").select("*").order("created_at", desc=True).execute()
    return result.data
