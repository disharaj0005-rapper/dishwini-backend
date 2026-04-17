from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from typing import Optional
from app.dependencies import require_admin
from app.database import get_db
from app.schemas.collection import (
    CollectionCreateRequest, CollectionUpdateRequest, CollectionResponse
)
from app.services.cloudinary_service import upload_image
from app.utils.security import generate_slug
from supabase import Client

router = APIRouter()


@router.get("")
async def list_collections(
    is_active: Optional[bool] = None,
    db: Client = Depends(get_db)
):
    """List all collections."""
    query = db.table("collections").select("*")
    if is_active is not None:
        query = query.eq("is_active", is_active)

    result = query.order("created_at", desc=True).execute()

    # Get product count for each collection
    collections = []
    for col in result.data:
        count = db.table("products").select("id", count="exact").eq(
            "collection_id", col["id"]
        ).eq("is_active", True).execute()
        col["product_count"] = count.count or 0
        collections.append(col)

    return collections


@router.get("/{collection_id}")
async def get_collection(collection_id: str, db: Client = Depends(get_db)):
    """Get a single collection with its products."""
    result = db.table("collections").select("*").eq("id", collection_id).execute()
    if not result.data:
        result = db.table("collections").select("*").eq("slug", collection_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Collection not found")

    collection = result.data[0]

    # Get products in this collection
    products = db.table("products").select("*").eq(
        "collection_id", collection["id"]
    ).eq("is_active", True).order("created_at", desc=True).execute()

    # Get images for each product
    for product in products.data:
        images = db.table("product_images").select("*").eq(
            "product_id", product["id"]
        ).order("display_order").execute()
        product["images"] = images.data

    collection["products"] = products.data
    return collection


@router.post("", status_code=201)
async def create_collection(
    request: CollectionCreateRequest,
    admin: dict = Depends(require_admin),
    db: Client = Depends(get_db)
):
    """Create a new collection (admin only)."""
    slug = generate_slug(request.name)

    collection_data = {
        "name": request.name,
        "slug": slug,
        "description": request.description,
        "banner_image": request.banner_image,
        "is_active": request.is_active
    }

    result = db.table("collections").insert(collection_data).execute()
    return result.data[0]


@router.post("/{collection_id}/banner")
async def upload_banner(
    collection_id: str,
    file: UploadFile = File(...),
    admin: dict = Depends(require_admin),
    db: Client = Depends(get_db)
):
    """Upload a banner image for a collection (admin only)."""
    existing = db.table("collections").select("id").eq("id", collection_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Collection not found")

    content = await file.read()
    result = await upload_image(content, f"dishwini/collections")

    db.table("collections").update(
        {"banner_image": result["url"]}
    ).eq("id", collection_id).execute()

    return {"banner_image": result["url"]}


@router.put("/{collection_id}")
async def update_collection(
    collection_id: str,
    request: CollectionUpdateRequest,
    admin: dict = Depends(require_admin),
    db: Client = Depends(get_db)
):
    """Update a collection (admin only)."""
    existing = db.table("collections").select("id").eq("id", collection_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Collection not found")

    update_data = request.model_dump(exclude_unset=True)
    result = db.table("collections").update(update_data).eq("id", collection_id).execute()
    return result.data[0]


@router.delete("/{collection_id}")
async def delete_collection(
    collection_id: str,
    admin: dict = Depends(require_admin),
    db: Client = Depends(get_db)
):
    """Delete a collection (admin only)."""
    db.table("collections").delete().eq("id", collection_id).execute()
    return {"message": "Collection deleted successfully"}
