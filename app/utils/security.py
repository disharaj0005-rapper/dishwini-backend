import re
import secrets
import string


def generate_slug(name: str) -> str:
    """Generate a URL-safe slug from a name."""
    slug = name.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[-\s]+', '-', slug)
    # Add random suffix to ensure uniqueness
    suffix = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(4))
    return f"{slug}-{suffix}"


def generate_sku(product_name: str, size: str = "", color: str = "") -> str:
    """Generate a SKU from product details."""
    parts = [
        product_name[:3].upper(),
        size[:2].upper() if size else "XX",
        color[:2].upper() if color else "XX",
        ''.join(secrets.choice(string.digits) for _ in range(4))
    ]
    return "-".join(parts)


def sanitize_input(text: str) -> str:
    """Basic input sanitization."""
    if not text:
        return text
    # Remove any HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()
