from pydantic import BaseModel
from typing import Optional, List


class CartAddRequest(BaseModel):
    product_variant_id: str
    quantity: int = 1


class CartItemResponse(BaseModel):
    id: str
    product_variant_id: str
    quantity: int
    product_name: Optional[str] = None
    product_slug: Optional[str] = None
    size: Optional[str] = None
    color: Optional[str] = None
    price: Optional[float] = None
    image_url: Optional[str] = None
    stock: Optional[int] = None


class CartResponse(BaseModel):
    items: List[CartItemResponse]
    total: float
    item_count: int
