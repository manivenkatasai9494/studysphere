from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.redis_client import rate_limit_check
from app.core.security import decode_token
from app.core.supabase_client import get_supabase

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    token = credentials.credentials
    payload = decode_token(token)

    if payload and payload.get("type") == "access":
        user_id = payload.get("sub")
        if user_id:
            return {"id": user_id, "token": token}

    # Validate via Supabase JWT
    try:
        sb = get_supabase()
        user = sb.auth.get_user(token)
        if user and user.user:
            return {"id": str(user.user.id), "email": user.user.email, "token": token}
    except Exception:
        pass

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


async def rate_limit_user(user: dict = Depends(get_current_user)) -> dict:
    key = f"rate:{user['id']}"
    if not rate_limit_check(key, limit=120, window=60):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")
    return user
