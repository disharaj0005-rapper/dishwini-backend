from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from typing import List, Optional
from app.dependencies import get_current_user, require_admin
from app.database import get_db
from app.schemas.product import (
    ProductCreateRequest, ProductUpdateRequest,
    ProductResponse, ProductListResponse, ProductVariantSchema
)
from app.services.cloudinary_service import upload_image, delete_image
from app.utils.security import generate_slug, generate_sku
from supabase import Client

router = APIRouter()


@router.get("", response_model=ProductListResponse)
async def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    collection_id: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    is_featured: Optional[bool] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    size: Optional[str] = None,
    color: Optional[str] = None,
    db: Client = Depends(get_db)
):
    """List products with filtering and pagination."""
    # If size or color filters are provided, first find matching product IDs from variants
    variant_product_ids = None
    if size or color:
        variant_query = db.table("product_variants").select("product_id")
        if size:
            variant_query = variant_query.eq("size", size)
        if color:
            variant_query = variant_query.eq("color", color)
        variant_result = variant_query.execute()
        variant_product_ids = list(set(v["product_id"] for v in variant_result.data))
        if not variant_product_ids:
            return ProductListResponse(products=[], total=0, page=page, page_size=page_size)

    query = db.table("products").select("*", count="exact").eq("is_active", True)

    if variant_product_ids is not None:
        query = query.in_("id", variant_product_ids)
    if collection_id:
        query = query.eq("collection_id", collection_id)
    if category:
        query = query.eq("category", category)
    if is_featured is not None:
        query = query.eq("is_featured", is_featured)
    if min_price is not None:
        query = query.gte("price", min_price)
    if max_price is not None:
        query = query.lte("price", max_price)
    if search:
        query = query.ilike("name", f"%{search}%")

    offset = (page - 1) * page_size
    result = query.order("created_at", desc=True).range(offset, offset + page_size - 1).execute()

    if not result.data:
        return ProductListResponse(
            products=[],
            total=result.count or 0,
            page=page,
            page_size=page_size
        )

    # Fetch images and variants in bulk
    product_ids = [p["id"] for p in result.data]
    
    images_res = db.table("product_images").select("*").in_("product_id", product_ids).order("display_order").execute()
    variants_res = db.table("product_variants").select("*").in_("product_id", product_ids).execute()

    # Map them to products
    images_by_product = {}
    for img in images_res.data:
        pid = img["product_id"]
        if pid not in images_by_product:
            images_by_product[pid] = []
        images_by_product[pid].append(img)

    variants_by_product = {}
    for var in variants_res.data:
        pid = var["product_id"]
        if pid not in variants_by_product:
            variants_by_product[pid] = []
        variants_by_product[pid].append(var)

    products = []
    for product in result.data:
        product["images"] = images_by_product.get(product["id"], [])
        product["variants"] = variants_by_product.get(product["id"], [])
        products.append(product)

    return ProductListResponse(
        products=products,
        total=result.count or 0,
        page=page,
        page_size=page_size
    )


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: str, db: Client = Depends(get_db)):
    """Get a single product with images and variants."""
    result = db.table("products").select("*").eq("id", product_id).execute()
    if not result.data:
        # Try by slug
        result = db.table("products").select("*").eq("slug", product_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Product not found")

    product = result.data[0]

    images = db.table("product_images").select("*").eq(
        "product_id", product["id"]
    ).order("display_order").execute()

    variants = db.table("product_variants").select("*").eq(
        "product_id", product["id"]
    ).execute()

    product["images"] = images.data
    product["variants"] = variants.data

    return product


@router.post("", response_model=ProductResponse, status_code=201)
async def create_product(
    request: ProductCreateRequest,
    admin: dict = Depends(require_admin),
    db: Client = Depends(get_db)
):
    """Create a new product (admin only)."""
    slug = generate_slug(request.name)

    product_data = {
        "name": request.name,
        "slug": slug,
        "description": request.description,
        "price": request.price,
        "compare_at_price": request.compare_at_price,
        "collection_id": request.collection_id,
        "category": request.category,
        "tags": request.tags,
        "is_active": request.is_active,
        "is_featured": request.is_featured
    }

    result = db.table("products").insert(product_data).execute()
    product = result.data[0]

    # Create variants if provided
    if request.variants:
        for variant in request.variants:
            variant_data = {
                "product_id": product["id"],
                "size": variant.size,
                "color": variant.color,
                "stock": variant.stock,
                "sku": variant.sku or generate_sku(request.name, variant.size or "", variant.color or ""),
                "price_override": variant.price_override
            }
            db.table("product_variants").insert(variant_data).execute()

    # Fetch complete product
    return await get_product(product["id"], db)


@router.post("/{product_id}/images")
async def upload_product_images(
    product_id: str,
    files: List[UploadFile] = File(...),
    admin: dict = Depends(require_admin),
    db: Client = Depends(get_db)
):
    """Upload images for a product (admin only)."""
    # Verify product exists
    product = db.table("products").select("id").eq("id", product_id).execute()
    if not product.data:
        raise HTTPException(status_code=404, detail="Product not found")

    # Get current max display order
    existing = db.table("product_images").select("display_order").eq(
        "product_id", product_id
    ).order("display_order", desc=True).limit(1).execute()
    start_order = (existing.data[0]["display_order"] + 1) if existing.data else 0

    uploaded = []
    for i, file in enumerate(files):
        content = await file.read()
        result = await upload_image(content, f"dishwini/products/{product_id}")
        image_data = {
            "product_id": product_id,
            "image_url": result["url"],
            "alt_text": file.filename,
            "display_order": start_order + i
        }
        img_result = db.table("product_images").insert(image_data).execute()
        uploaded.append(img_result.data[0])

    return {"uploaded": uploaded, "count": len(uploaded)}


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: str,
    request: ProductUpdateRequest,
    admin: dict = Depends(require_admin),
    db: Client = Depends(get_db)
):
    """Update a product (admin only)."""
    existing = db.table("products").select("id").eq("id", product_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Product not found")

    update_data = request.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    db.table("products").update(update_data).eq("id", product_id).execute()
    return await get_product(product_id, db)


@router.delete("/{product_id}")
async def delete_product(
    product_id: str,
    admin: dict = Depends(require_admin),
    db: Client = Depends(get_db)
):
    """Delete a product (admin only)."""
    existing = db.table("products").select("id").eq("id", product_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Product not found")

    # Check if product is in any orders
    variants = db.table("product_variants").select("id").eq("product_id", product_id).execute()
    if variants.data:
        variant_ids = [v["id"] for v in variants.data]
        orders = db.table("order_items").select("id").in_("product_variant_id", variant_ids).limit(1).execute()
        if orders.data:
            # Soft delete instead of hard delete to preserve order history
            db.table("products").update({"is_active": False}).eq("id", product_id).execute()
            return {"message": "Product is part of existing orders and was deactivated instead of deleted to preserve history."}

    # Delete images from Cloudinary
    images = db.table("product_images").select("image_url").eq("product_id", product_id).execute()
    for img in images.data:
        try:
            # Extract public_id from URL for deletion
            url = img["image_url"]
            if "cloudinary" in url:
                public_id = "/".join(url.split("/")[-3:]).split(".")[0]
                await delete_image(public_id)
        except Exception:
            pass

    db.table("products").delete().eq("id", product_id).execute()
    return {"message": "Product deleted successfully"}


@router.post("/{product_id}/variants", response_model=ProductResponse)
async def add_variant(
    product_id: str,
    variant: ProductVariantSchema,
    admin: dict = Depends(require_admin),
    db: Client = Depends(get_db)
):
    """Add a variant to a product (admin only)."""
    existing = db.table("products").select("id, name").eq("id", product_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Product not found")

    variant_data = {
        "product_id": product_id,
        "size": variant.size,
        "color": variant.color,
        "stock": variant.stock,
        "sku": variant.sku or generate_sku(
            existing.data[0]["name"], variant.size or "", variant.color or ""
        ),
        "price_override": variant.price_override
    }
    db.table("product_variants").insert(variant_data).execute()
    return await get_product(product_id, db)


@router.put("/variants/{variant_id}")
async def update_variant(
    variant_id: str,
    variant: ProductVariantSchema,
    admin: dict = Depends(require_admin),
    db: Client = Depends(get_db)
):
    """Update a product variant (admin only)."""
    update_data = variant.model_dump(exclude_unset=True, exclude={"id"})
    result = db.table("product_variants").update(update_data).eq("id", variant_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Variant not found")
    return result.data[0]


@router.delete("/variants/{variant_id}")
async def delete_variant(
    variant_id: str,
    admin: dict = Depends(require_admin),
    db: Client = Depends(get_db)
):
    """Delete a product variant (admin only)."""
    # Verify it's not the only variant (optional, but good practice)
    variant = db.table("product_variants").select("product_id").eq("id", variant_id).execute()
    if not variant.data:
        raise HTTPException(status_code=404, detail="Variant not found")
    
    # Check if variant is in any orders
    orders = db.table("order_items").select("id").eq("product_variant_id", variant_id).limit(1).execute()
    if orders.data:
        raise HTTPException(
            status_code=400, 
            detail="Cannot delete this variant because it is part of existing orders. Please set its stock to 0 instead."
        )

    product_id = variant.data[0]["product_id"]
    all_variants = db.table("product_variants").select("id").eq("product_id", product_id).execute()
    
    if len(all_variants.data) <= 1:
        raise HTTPException(status_code=400, detail="Cannot delete the last variant of a product.")

    db.table("product_variants").delete().eq("id", variant_id).execute()
    return {"message": "Variant deleted successfully"}
