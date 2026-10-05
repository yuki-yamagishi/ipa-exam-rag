"""Google OAuth 2.0 authentication and session management API router."""

import logging
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from src.infrastructure.auth_provider import GoogleAuthProvider
from src.infrastructure.config import Settings
from src.presentation.api.deps import get_auth_provider, get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class AuthStatusResponse(BaseModel):
    auth_enabled: bool
    authenticated: bool
    user_email: str | None


class LoginUrlResponse(BaseModel):
    login_url: str
    state: str


class LogoutResponse(BaseModel):
    success: bool
    message: str


@router.get(
    "/status",
    response_model=AuthStatusResponse,
    summary="Get current user authentication status and session state",
)
def get_auth_status(
    settings: Annotated[Settings, Depends(get_settings)],
    auth_provider: Annotated[GoogleAuthProvider, Depends(get_auth_provider)],
    session_user: Annotated[str | None, Cookie()] = None,
) -> AuthStatusResponse:
    """Return whether authentication is enabled and current user email if authenticated."""
    if not settings.auth_enabled:
        return AuthStatusResponse(auth_enabled=False, authenticated=True, user_email=None)

    if not session_user:
        return AuthStatusResponse(auth_enabled=True, authenticated=False, user_email=None)

    email = auth_provider.verify_session_token(session_user)
    if not email:
        return AuthStatusResponse(auth_enabled=True, authenticated=False, user_email=None)

    if not auth_provider.is_email_allowed(email):
        return AuthStatusResponse(auth_enabled=True, authenticated=False, user_email=None)

    return AuthStatusResponse(auth_enabled=True, authenticated=True, user_email=email)


@router.get(
    "/login",
    response_model=LoginUrlResponse,
    summary="Get Google OAuth 2.0 authorization URL",
)
def get_login_url(
    auth_provider: Annotated[GoogleAuthProvider, Depends(get_auth_provider)],
) -> LoginUrlResponse:
    """Generate and return Google OAuth login URL with cryptographically signed CSRF state."""
    state = auth_provider.generate_state()
    login_url = auth_provider.get_authorization_url(state=state)
    return LoginUrlResponse(login_url=login_url, state=state)


@router.get(
    "/callback",
    summary="Handle Google OAuth 2.0 authorization callback and set session cookie",
)
def oauth_callback(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    auth_provider: Annotated[GoogleAuthProvider, Depends(get_auth_provider)],
    code: Annotated[str | None, Query(description="Google OAuth authorization code")] = None,
    state: Annotated[str | None, Query(description="CSRF state token")] = None,
    error: Annotated[str | None, Query(description="Google OAuth error reason")] = None,
) -> RedirectResponse:
    """Verify state token, exchange code for user profile, verify whitelist, and set session cookie."""
    if error or not code or not state:
        logger.warning("OAuth authorization rejected or cancelled: error=%s", error)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Google OAuth 認可が拒否または中断されました: {error or 'パラメータ不足'}",
        )

    if not auth_provider.verify_state(state):
        logger.warning("OAuth callback failed state verification: %s", state)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="無効な state パラメータまたは CSRF 検証失敗です。",
        )

    try:
        user_info = auth_provider.exchange_code_for_user(code)
    except Exception as e:
        logger.error("OAuth code exchange failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Google OAuth 認証に失敗しました: {e}",
        ) from e

    email = user_info.get("email") if isinstance(user_info, dict) else None
    if not email or not auth_provider.is_email_allowed(email):
        logger.warning("Unauthorized user email attempt: %s", email)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"メールアドレス '{email}' はアクセスが許可されていません。",
        )

    is_secure = settings.cookie_secure or (request.url.scheme == "https")
    session_token = auth_provider.generate_session_token(email)
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="session_user",
        value=session_token,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        max_age=604800,  # 7 days
        path="/",
    )
    return response


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Log out and clear session cookie",
)
def logout(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> JSONResponse:
    """Clear session cookie and log out."""
    is_secure = settings.cookie_secure or (request.url.scheme == "https")
    response = JSONResponse(
        content={"success": True, "message": "ログアウトしました。"},
        status_code=status.HTTP_200_OK,
    )
    response.delete_cookie(
        key="session_user",
        path="/",
        httponly=True,
        secure=is_secure,
        samesite="lax",
    )
    return response
