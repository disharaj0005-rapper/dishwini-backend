from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ProductImageSchema(BaseModel):
    id: Optional[str] = None
    image_url: str
    alt_text: Optional[str] = None
    display_order: int = 0


class ProductVariantSchema(BaseModel):
    id: Optional[str] = None
    size: Optional[str] = None
    color: Optional[str] = None
    stock: int = 0
    sku: Optional[str] = None
    price_override: Optional[float] = None


class ProductCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    compare_at_price: Optional[float] = None
    collection_id: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    is_active: bool = True
    is_featured: bool = False
    variants: Optional[List[ProductVariantSchema]] = None


class ProductUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    compare_at_price: Optional[float] = None
    collection_id: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None


class ProductResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: Optional[str] = None
    price: float
    compare_at_price: Optional[float] = None
    collection_id: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    is_active: bool
    is_featured: bool
    images: Optional[List[ProductImageSchema]] = None
    variants: Optional[List[ProductVariantSchema]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ProductListResponse(BaseModel):
    products: List[ProductResponse]
    total: int
    page: int
    page_size: int
