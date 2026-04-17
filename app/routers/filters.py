from fastapi import APIRouter, Depends
from app.database import get_db
from supabase import Client

router = APIRouter()


@router.get("/options")
async def get_filter_options(db: Client = Depends(get_db)):
    """Return available filter options (sizes, colors, price range)."""
    # Get distinct sizes
    sizes_result = db.table("product_variants").select("size").not_.is_("size", "null").execute()
    sizes = sorted(set(v["size"] for v in sizes_result.data if v["size"]))

    # Get distinct colors
    colors_result = db.table("product_variants").select("color").not_.is_("color", "null").execute()
    colors = sorted(set(v["color"] for v in colors_result.data if v["color"]))

    # Get price range from active products
    min_result = db.table("products").select("price").eq("is_active", True).order("price").limit(1).execute()
    max_result = db.table("products").select("price").eq("is_active", True).order("price", desc=True).limit(1).execute()

    price_min = min_result.data[0]["price"] if min_result.data else 0
    price_max = max_result.data[0]["price"] if max_result.data else 10000

    return {
        "sizes": sizes,
        "colors": colors,
        "price_range": {"min": price_min, "max": price_max}
    }
