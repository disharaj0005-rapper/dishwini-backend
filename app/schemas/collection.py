from pydantic import BaseModel
from typing import Optional, List


class CollectionCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    banner_image: Optional[str] = None
    is_active: bool = True


class CollectionUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    banner_image: Optional[str] = None
    is_active: Optional[bool] = None


class CollectionResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: Optional[str] = None
    banner_image: Optional[str] = None
    is_active: bool
    product_count: Optional[int] = 0
    created_at: Optional[str] = None
