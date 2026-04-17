from pydantic import BaseModel, EmailStr
from typing import Optional


class TokenVerifyRequest(BaseModel):
    token: str


class TokenVerifyResponse(BaseModel):
    valid: bool
    user_id: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    source: Optional[str] = "store"
    admin_secret: Optional[str] = None

class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str
    source: Optional[str] = "store"

class ForgotPasswordRequest(BaseModel):
    email: EmailStr
    source: Optional[str] = "store"

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str
    source: Optional[str] = "store"

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict
