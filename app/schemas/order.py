from pydantic import BaseModel
from typing import Optional, List


class OrderItemResponse(BaseModel):
    id: str
    product_variant_id: str
    product_name: str
    variant_info: Optional[str] = None
    quantity: int
    price: float
    image_url: Optional[str] = None


class AddressInput(BaseModel):
    name: str
    phone: str
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: str
    pincode: str
    country: str = "India"


class OrderCreateRequest(BaseModel):
    address_id: Optional[str] = None
    shipping_address: Optional[AddressInput] = None
    coupon_code: Optional[str] = None
    notes: Optional[str] = None
    payment_method: str = "cod"


class OrderUpdateRequest(BaseModel):
    status: Optional[str] = None
    payment_status: Optional[str] = None
    payment_method: Optional[str] = None


class OrderResponse(BaseModel):
    id: str
    order_number: str
    user_id: str
    status: str
    total_amount: float
    shipping_amount: float = 0
    discount_amount: float = 0
    payment_status: str
    payment_method: Optional[str] = "cod"
    shipping_address: Optional[dict] = None
    items: Optional[List[OrderItemResponse]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class OrderListResponse(BaseModel):
    orders: List[OrderResponse]
    total: int
