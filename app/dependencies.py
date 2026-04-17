from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from app.config import get_settings
from app.database import get_db
from supabase import Client

security = HTTPBearer()
settings = get_settings()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Client = Depends(get_db)
) -> dict:
    """Verify JWT token and return the current user."""
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
        # Fetch user from database
        result = db.table("users").select("*").eq("id", user_id).execute()
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        user = result.data[0]
        # Strip sensitive fields before returning
        user.pop("password_hash", None)
        return user
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )


async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Require the current user to be an admin."""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user
