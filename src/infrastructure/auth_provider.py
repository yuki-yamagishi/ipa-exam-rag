"""Google OAuth 2.0 / OpenID Connect authentication provider with email whitelist guard."""

import base64
import hashlib
import hmac
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from src.infrastructure.config import settings

logger = logging.getLogger(__name__)

GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"


class GoogleAuthProvider:
    """Zero-dependency Google OAuth 2.0 authentication provider using standard urllib."""

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        redirect_uri: str | None = None,
        allowed_emails: list[str] | None = None,
        session_secret: str | None = None,
    ):
        self.client_id = client_id or settings.google_client_id
        self.client_secret = client_secret or settings.google_client_secret
        self.redirect_uri = redirect_uri or settings.google_redirect_uri
        self.allowed_emails = (
            allowed_emails if allowed_emails is not None else settings.allowed_emails
        )
        self.session_secret = session_secret or settings.session_secret

    def _get_signing_secret(self) -> bytes:
        """Get secret key for HMAC token signing, preferring dedicated session_secret."""
        key = self.session_secret or self.client_secret
        if not key:
            if settings.auth_enabled:
                logger.warning(
                    "Neither session_secret nor google_client_secret is set while auth_enabled=True. "
                    "Falling back to default salt. Please configure SESSION_SECRET in production!"
                )
            key = "ipa-exam-rag-default-oauth-salt"
        return key.encode("utf-8")

    def generate_state(self) -> str:
        """Generate a cryptographically signed, timestamped CSRF state token."""
        secret = self._get_signing_secret()
        timestamp = str(int(time.time()))
        sig = hmac.new(secret, timestamp.encode("utf-8"), hashlib.sha256).hexdigest()
        token = f"{timestamp}:{sig}"
        return base64.urlsafe_b64encode(token.encode("utf-8")).decode("utf-8")

    def verify_state(self, state: str, max_age_seconds: int = 600) -> bool:
        """Verify the cryptographically signed state token and check expiration."""
        if not state:
            return False
        try:
            decoded = base64.urlsafe_b64decode(state.encode("utf-8")).decode("utf-8")
            parts = decoded.rsplit(":", 1)
            if len(parts) != 2:
                return False
            timestamp_str, signature = parts
            timestamp = int(timestamp_str)

            now = int(time.time())
            # Allow 30 seconds of clock skew
            if now - timestamp < -30 or now - timestamp > max_age_seconds:
                return False

            secret = self._get_signing_secret()
            expected_sig = hmac.new(
                secret, timestamp_str.encode("utf-8"), hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(signature, expected_sig)
        except Exception:
            return False

    def get_authorization_url(
        self, state: str | None = None, redirect_uri: str | None = None
    ) -> str:
        """Generate Google OAuth 2.0 login URL."""
        state_token = state or self.generate_state()
        uri = redirect_uri or self.redirect_uri
        params = {
            "client_id": self.client_id,
            "redirect_uri": uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state_token,
            "access_type": "online",
            "prompt": "select_account",
        }
        return f"{GOOGLE_AUTH_ENDPOINT}?{urllib.parse.urlencode(params)}"

    def exchange_code_for_user(self, code: str, redirect_uri: str | None = None) -> dict[str, Any]:
        """Exchange authorization code for access token and fetch user profile.

        Raises:
            RuntimeError: If token exchange or user info retrieval fails.
        """
        uri = redirect_uri or self.redirect_uri

        # 1. Exchange authorization code for token
        data = urllib.parse.urlencode(
            {
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": uri,
                "grant_type": "authorization_code",
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            GOOGLE_TOKEN_ENDPOINT,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                token_data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            logger.error("Failed to exchange code for token: %s", e)
            raise RuntimeError(f"Google OAuth token exchange failed: {e}") from e

        access_token = token_data.get("access_token")
        if not access_token:
            raise RuntimeError("Access token missing in Google OAuth response.")

        # 2. Fetch User Profile
        user_req = urllib.request.Request(
            GOOGLE_USERINFO_ENDPOINT,
            headers={"Authorization": f"Bearer {access_token}"},
            method="GET",
        )

        try:
            with urllib.request.urlopen(user_req, timeout=10.0) as resp:
                user_info: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            logger.error("Failed to fetch user info: %s", e)
            raise RuntimeError(f"Google OAuth user info fetch failed: {e}") from e

        return user_info

    def is_email_allowed(self, email: str | None) -> bool:
        """Check whether the given email address is authorized.

        Normalizes email casing and trims surrounding whitespace.
        If allowed_emails list is empty, denies all access by default for security.
        """
        if not email or not self.allowed_emails:
            return False

        normalized_email = email.strip().lower()
        normalized_allowed = {e.strip().lower() for e in self.allowed_emails if e.strip()}

        return normalized_email in normalized_allowed

    def generate_session_token(self, email: str, max_age_days: int = 7) -> str:
        """Generate a cryptographically signed HMAC-SHA256 session token for authenticated user."""
        secret = self._get_signing_secret()
        expires_at = str(int(time.time()) + max_age_days * 86400)
        payload = f"{email.strip().lower()}:{expires_at}"
        sig = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
        token = f"{payload}:{sig}"
        return base64.urlsafe_b64encode(token.encode("utf-8")).decode("utf-8")

    def verify_session_token(self, token: str | None) -> str | None:
        """Verify HMAC-SHA256 signed session token. Returns normalized email if valid, else None."""
        if not token:
            return None
        try:
            decoded = base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")
            parts = decoded.rsplit(":", 2)
            if len(parts) != 3:
                return None
            email, expires_at_str, signature = parts
            expires_at = int(expires_at_str)

            now = int(time.time())
            if now > expires_at:
                return None

            secret = self._get_signing_secret()
            payload = f"{email}:{expires_at_str}"
            expected_sig = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
            if hmac.compare_digest(signature, expected_sig):
                return email
            return None
        except Exception:
            return None
