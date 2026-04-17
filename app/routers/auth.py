from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
import random
import string
from datetime import datetime, timedelta, timezone
from app.dependencies import get_current_user
from app.database import get_db
from app.schemas.auth import (
    TokenVerifyRequest, TokenVerifyResponse,
    UserRegisterRequest, UserLoginRequest, AuthResponse,
    ForgotPasswordRequest, ResetPasswordRequest
)
from app.utils.auth_utils import hash_password, verify_password, create_access_token, verify_token
from app.services.mail_service import send_email
from app.config import get_settings
from supabase import Client

settings = get_settings()

router = APIRouter()





@router.post("/register", response_model=AuthResponse)
async def register_user(request: UserRegisterRequest, db: Client = Depends(get_db)):
    """Register a new user with email and password."""
    try:
        # Check if user already exists
        existing = db.table("users").select("id").eq("email", request.email).execute()
        if existing.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already exists"
            )

        # Validate admin secret if source is admin
        user_role = "customer"
        if request.source == "admin":
            if not request.admin_secret or request.admin_secret != settings.ADMIN_REGISTRATION_SECRET:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid Admin Secret Key"
                )
            user_role = "admin"

        # Hash the password and create user record
        user_data = {
            "email": request.email,
            "password_hash": hash_password(request.password),
            "full_name": request.full_name,
            "role": user_role
        }
        result = db.table("users").insert(user_data).execute()
        user = result.data[0]

        # Generate JWT token
        token = create_access_token(
            user_id=user["id"],
            email=user["email"],
            role=user.get("role", "customer")
        )

        return AuthResponse(
            access_token=token,
            user={
                "id": user["id"],
                "email": user["email"],
                "full_name": user.get("full_name"),
                "role": user.get("role", "customer")
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )


@router.post("/login", response_model=AuthResponse)
async def login_user(request: UserLoginRequest, db: Client = Depends(get_db)):
    """Login with email and password."""
    # Fetch user by email
    result = db.table("users").select("*").eq("email", request.email).execute()
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    user = result.data[0]

    # Verify password
    if not user.get("password_hash") or not verify_password(request.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Verify admin source has admin role
    if request.source == "admin" and user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin privileges required."
        )

    # Generate JWT token
    token = create_access_token(
        user_id=user["id"],
        email=user["email"],
        role=user.get("role", "customer")
    )

    return AuthResponse(
        access_token=token,
        user={
            "id": user["id"],
            "email": user["email"],
            "full_name": user.get("full_name"),
            "role": user.get("role", "customer")
        }
    )


@router.post("/verify-token", response_model=TokenVerifyResponse)
async def verify_user_token(request: TokenVerifyRequest, db: Client = Depends(get_db)):
    """Verify a JWT token."""
    try:
        payload = verify_token(request.token)
        user_id = payload.get("sub")

        # Fetch user from database to get latest role
        result = db.table("users").select("*").eq("id", user_id).execute()
        user = result.data[0] if result.data else None

        return TokenVerifyResponse(
            valid=True,
            user_id=user_id,
            email=payload.get("email"),
            role=user.get("role", "customer") if user else payload.get("role", "customer")
        )
    except Exception:
        return TokenVerifyResponse(valid=False)


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get current authenticated user."""
    return current_user


@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest, db: Client = Depends(get_db)):
    """Generate OTP and send via EmailJS to reset password."""
    # Check if user exists and fetch role
    result = db.table("users").select("id, role").eq("email", request.email).execute()
    if not result.data:
        # Don't leak whether user exists
        return {"message": "If that email is in our database, we have sent a reset link"}

    user = result.data[0]
    user_id = user["id"]
    user_role = user.get("role", "customer")

    # Enforce origin access: Customers cannot reset from Admin panel
    if request.source == "admin" and user_role != "admin":
        # Don't leak that it failed due to role
        return {"message": "If that email is in our database, we have sent a reset link"}
    
    # Generate 6 digit OTP
    otp = ''.join(random.choices(string.digits, k=6))
    
    # Store OTP in DB
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    reset_data = {
        "user_id": user_id,
        "email": request.email,
        "otp": otp,
        "expires_at": expires_at
    }
    
    try:
        db.table("password_resets").insert(reset_data).execute()
    except Exception as e:
        print(f"Error inserting OTP: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Database setup incomplete for password reset. Please create password_resets table via SQL script."
        )

    # Send EmailJS
    template_params = {
        "to_email": request.email,
        "passcode": otp,
        "time": "10 minutes"
    }
    
    if settings.EMAILJS_SERVICE_ID and settings.EMAILJS_OTP_TEMPLATE_ID:
        success = await send_email(settings.EMAILJS_OTP_TEMPLATE_ID, template_params)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to send OTP email")
    else:
        print(f"WARNING: EmailJS not configured. OTP generated is {otp}")
        
    return {"message": "If that email is in our database, we have sent a reset link"}


@router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest, db: Client = Depends(get_db)):
    """Verify OTP and update password."""
    # Verify OTP
    result = db.table("password_resets").select("*").eq("email", request.email).eq("otp", request.otp).execute()
    
    if not result.data:
        raise HTTPException(status_code=400, detail="Invalid reset code or email.")
        
    reset_record = result.data[-1]  # Get the latest one if multiple
    
    # Check expiry
    # Improved timestamp parsing for robustness
    expires_at_str = reset_record.get("expires_at", "")
    try:
        if isinstance(expires_at_str, str):
            if expires_at_str.endswith('Z'):
                expires_at_str = expires_at_str[:-1] + '+00:00'
            elif ' ' in expires_at_str and '+' not in expires_at_str:
                # Handle space instead of T
                expires_at_str = expires_at_str.replace(' ', 'T')
            
            expires_at_dt = datetime.fromisoformat(expires_at_str)
            # Ensure it's timezone-aware for comparison
            if expires_at_dt.tzinfo is None:
                expires_at_dt = expires_at_dt.replace(tzinfo=timezone.utc)
        else:
            raise ValueError("Invalid expiry format")
            
        if datetime.now(timezone.utc) > expires_at_dt:
            raise HTTPException(status_code=400, detail="The reset code has expired. Please request a new one.")
            
    except (ValueError, TypeError) as e:
        print(f"ISO format error: {e}")
        raise HTTPException(status_code=400, detail="Invalid reset code. Please try again.")
        
    # Update password
    hashed_password = hash_password(request.new_password)
    update_res = db.table("users").update({"password_hash": hashed_password}).eq("email", request.email).execute()
    
    if not update_res.data:
        raise HTTPException(status_code=500, detail="Failed to update password. User might have been deleted.")

    # Delete the used OTP
    db.table("password_resets").delete().eq("id", reset_record["id"]).execute()
    
    return {"message": "Password has been successfully reset. You can now login with your new password."}
