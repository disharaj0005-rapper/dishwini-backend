from pydantic import BaseModel, EmailStr
from typing import Optional, List


class UserProfileResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    phone: Optional[str] = None
    role: str
    avatar_url: Optional[str] = None
    created_at: Optional[str] = None


class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None


class AddressResponse(BaseModel):
    id: str
    name: str
    phone: str
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: str
    pincode: str
    country: str
    is_default: bool = False


class AddressCreateRequest(BaseModel):
    name: str
    phone: str
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: str
    pincode: str
    country: str = "India"
    is_default: bool = False
