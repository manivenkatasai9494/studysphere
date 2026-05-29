from fastapi import APIRouter, HTTPException, status

from app.core.security import create_access_token, create_refresh_token, decode_token
from app.core.supabase_client import get_supabase, get_supabase_anon
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse)
async def register(body: RegisterRequest):
    sb = get_supabase_anon()
    try:
        result = sb.auth.sign_up({
            "email": body.email,
            "password": body.password,
            "options": {"data": {"full_name": body.full_name or ""}},
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not result.user:
        raise HTTPException(status_code=400, detail="Registration failed")

    user_id = str(result.user.id)
    access = create_access_token(user_id, {"email": body.email})
    refresh = create_refresh_token(user_id)

    if result.session:
        access = result.session.access_token
        refresh = result.session.refresh_token or refresh

    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        user_id=user_id,
        email=body.email,
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    sb = get_supabase_anon()
    try:
        result = sb.auth.sign_in_with_password({"email": body.email, "password": body.password})
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not result.user or not result.session:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user_id = str(result.user.id)
    return TokenResponse(
        access_token=result.session.access_token,
        refresh_token=result.session.refresh_token or create_refresh_token(user_id),
        user_id=user_id,
        email=body.email,
    )


@router.post("/logout")
async def logout():
    return {"message": "Logged out successfully. Clear tokens on client."}


@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordRequest):
    sb = get_supabase_anon()
    try:
        sb.auth.reset_password_email(body.email)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": "Password reset email sent if account exists."}


@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest):
    sb = get_supabase_anon()
    try:
        sb.auth.update_user({"password": body.password})
    except Exception:
        try:
            get_supabase().auth.admin.update_user_by_id(body.token, {"password": body.password})
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    return {"message": "Password updated successfully."}


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshTokenRequest):
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        sb = get_supabase_anon()
        try:
            result = sb.auth.refresh_session(body.refresh_token)
            if result.session:
                return TokenResponse(
                    access_token=result.session.access_token,
                    refresh_token=result.session.refresh_token,
                    user_id=str(result.user.id),
                    email=result.user.email,
                )
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_id = payload["sub"]
    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
        user_id=user_id,
    )
