from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
import bcrypt
from app.config import get_settings

settings = get_settings()


def hash_password(password: str) -> str:
    """Hash a plain-text password using bcrypt."""
    pwd_bytes = password.encode('utf-8')
    # Use a salt with 12 rounds (default is 12)
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    try:
        pwd_bytes = plain_password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(pwd_bytes, hashed_bytes)
    except Exception:
        return False


def create_access_token(user_id: str, email: str, role: str = "customer") -> str:
    """Create a JWT access token."""
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRATION_HOURS)
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def verify_token(token: str) -> dict:
    """Verify a JWT token and return the payload."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError as e:
        raise ValueError(f"Token verification failed: {str(e)}")
