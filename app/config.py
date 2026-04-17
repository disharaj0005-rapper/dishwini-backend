from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Supabase (database only)
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    # JWT Auth
    JWT_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24

    # Cloudinary
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""

    # Razorpay
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""

    # EmailJS
    EMAILJS_SERVICE_ID: str = ""
    EMAILJS_OTP_TEMPLATE_ID: str = ""
    EMAILJS_CONTACT_TEMPLATE_ID: str = ""
    EMAILJS_PUBLIC_KEY: str = ""
    EMAILJS_PRIVATE_KEY: str = ""

    # App
    APP_ENV: str = "development"
    FRONTEND_URL: str = "http://localhost:3000"
    ADMIN_URL: str = "http://localhost:3001"
    ADMIN_REGISTRATION_SECRET: str = "DishwiniAdmin2026"

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()
