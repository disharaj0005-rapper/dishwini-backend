import cloudinary
import cloudinary.uploader
from app.config import get_settings

settings = get_settings()

cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True
)


async def upload_image(file, folder: str = "dishwini/products") -> dict:
    """Upload image to Cloudinary and return URL and public_id."""
    try:
        result = cloudinary.uploader.upload(
            file,
            folder=folder,
            transformation=[
                {"quality": "auto", "fetch_format": "auto"}
            ]
        )
        return {
            "url": result["secure_url"],
            "public_id": result["public_id"],
            "width": result.get("width"),
            "height": result.get("height")
        }
    except Exception as e:
        raise Exception(f"Image upload failed: {str(e)}")


async def delete_image(public_id: str) -> bool:
    """Delete image from Cloudinary by public_id."""
    try:
        result = cloudinary.uploader.destroy(public_id)
        return result.get("result") == "ok"
    except Exception as e:
        raise Exception(f"Image deletion failed: {str(e)}")
