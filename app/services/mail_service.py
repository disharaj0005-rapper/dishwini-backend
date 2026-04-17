import httpx
from app.config import get_settings

settings = get_settings()

async def send_email(template_id: str, template_params: dict) -> bool:
    """Send an email using EmailJS REST API."""
    try:
        payload = {
            "service_id": settings.EMAILJS_SERVICE_ID,
            "template_id": template_id,
            "user_id": settings.EMAILJS_PUBLIC_KEY,
            "accessToken": settings.EMAILJS_PRIVATE_KEY,
            "template_params": template_params
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.emailjs.com/api/v1.0/email/send",
                json=payload,
                timeout=10.0
            )
            if response.status_code >= 400:
                print(f"EmailJS API Error ({response.status_code}): {response.text}")
            response.raise_for_status()
        return True
    except Exception as e:
        print(f"Email sending failed: {str(e)}")
        return False


async def send_order_confirmation(to: str, order_number: str, total: float):
    """Send order confirmation email."""
    # Assuming the user creates a template for orders that expects order_number and total
    template_params = {
        "to_email": to,
        "order_number": order_number,
        "total": f"₹{total:,.2f}"
    }
    # Using a placeholder template ID that can be added to config later if needed
    # Or utilizing the OTP template temporarily for simplicity (not ideal, but prevents crash)
    print(f"Would send order confirmation to {to} for order {order_number} using EmailJS.")
    # uncomment below when EMAILJS_ORDER_TEMPLATE_ID is in config
    # await send_email(settings.EMAILJS_ORDER_TEMPLATE_ID, template_params)
