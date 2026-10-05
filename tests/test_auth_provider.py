"""Unit tests for GoogleAuthProvider."""

import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.auth_provider import GoogleAuthProvider
from src.infrastructure.config import Settings


def test_get_authorization_url():
    provider = GoogleAuthProvider(
        client_id="test-client-id.apps.googleusercontent.com",
        client_secret="test-secret",
        redirect_uri="https://my-app.run.app",
    )
    url = provider.get_authorization_url(state="xyz123")

    assert "https://accounts.google.com/o/oauth2/v2/auth" in url
    assert "client_id=test-client-id.apps.googleusercontent.com" in url
    assert "redirect_uri=https%3A%2F%2Fmy-app.run.app" in url
    assert "state=xyz123" in url
    assert "scope=openid+email+profile" in url


def test_is_email_allowed_normalization():
    provider = GoogleAuthProvider(allowed_emails=["Student@Example.COM ", "admin@domain.org"])

    # Exact match normalized
    assert provider.is_email_allowed("student@example.com") is True
    assert provider.is_email_allowed("STUDENT@EXAMPLE.COM") is True
    assert provider.is_email_allowed("  student@example.com  ") is True
    assert provider.is_email_allowed("admin@domain.org") is True

    # Unauthorized
    assert provider.is_email_allowed("attacker@gmail.com") is False
    assert provider.is_email_allowed("other@example.com") is False

    # Boundary: Empty / None
    assert provider.is_email_allowed("") is False
    assert provider.is_email_allowed(None) is False


def test_is_email_allowed_empty_whitelist_denies_all():
    # If no emails specified in whitelist, deny everything
    provider = GoogleAuthProvider(allowed_emails=[])
    assert provider.is_email_allowed("anyone@gmail.com") is False


def test_exchange_code_for_user_success():
    provider = GoogleAuthProvider(
        client_id="cid",
        client_secret="sec",
        redirect_uri="https://app.run.app",
    )

    fake_token_resp = json.dumps({"access_token": "fake-access-token"}).encode("utf-8")
    fake_user_resp = json.dumps(
        {
            "email": "user@example.com",
            "name": "Test User",
            "picture": "https://example.com/pic.jpg",
        }
    ).encode("utf-8")

    mock_resp_token = MagicMock()
    mock_resp_token.read.return_value = fake_token_resp
    mock_resp_token.__enter__.return_value = mock_resp_token

    mock_resp_user = MagicMock()
    mock_resp_user.read.return_value = fake_user_resp
    mock_resp_user.__enter__.return_value = mock_resp_user

    with patch(
        "urllib.request.urlopen", side_effect=[mock_resp_token, mock_resp_user]
    ) as mock_urlopen:
        user_info = provider.exchange_code_for_user(code="valid-auth-code")

        assert user_info["email"] == "user@example.com"
        assert user_info["name"] == "Test User"
        assert mock_urlopen.call_count == 2


def test_exchange_code_for_user_error_handling():
    provider = GoogleAuthProvider(
        client_id="cid",
        client_secret="sec",
        redirect_uri="https://app.run.app",
    )

    with patch(
        "urllib.request.urlopen",
        side_effect=urllib.error.HTTPError(
            url="https://oauth2.googleapis.com/token",
            code=400,
            msg="Bad Request",
            hdrs={},
            fp=None,
        ),
    ):
        with pytest.raises(RuntimeError, match="Google OAuth token exchange failed"):
            provider.exchange_code_for_user(code="invalid-code")


def test_settings_allowed_emails_parsing(monkeypatch):
    """Verify Settings parses single strings, comma-separated lists, and JSON arrays."""
    # Single email string (common in Cloud Run --set-env-vars)
    s1 = Settings(allowed_emails="student@example.com")
    assert s1.allowed_emails == ["student@example.com"]

    # Comma-separated email string
    s2 = Settings(allowed_emails="user1@gmail.com, user2@gmail.com ,  admin@domain.org ")
    assert s2.allowed_emails == ["user1@gmail.com", "user2@gmail.com", "admin@domain.org"]

    # JSON array string
    s3 = Settings(allowed_emails='["a@test.com", "b@test.com"]')
    assert s3.allowed_emails == ["a@test.com", "b@test.com"]

    # Native list
    s4 = Settings(allowed_emails=["c@test.com", "d@test.com"])
    assert s4.allowed_emails == ["c@test.com", "d@test.com"]

    # Empty / whitespace
    s5 = Settings(allowed_emails="   ")
    assert s5.allowed_emails == []

    # Direct environment variable loading (Cloud Run runtime simulation)
    monkeypatch.setenv("ALLOWED_EMAILS", "student@example.com")
    s_env1 = Settings()
    assert s_env1.allowed_emails == ["student@example.com"]

    monkeypatch.setenv("ALLOWED_EMAILS", "user1@gmail.com,user2@gmail.com")
    s_env2 = Settings()
    assert s_env2.allowed_emails == ["user1@gmail.com", "user2@gmail.com"]

    # Unquoted bracketed string (e.g. gcloud CLI formatted string)
    monkeypatch.setenv("ALLOWED_EMAILS", "[student@example.com]")
    s_env3 = Settings()
    assert s_env3.allowed_emails == ["student@example.com"]


def test_hmac_state_token_verification():
    """Verify cryptographically signed HMAC state token generation and verification."""
    provider = GoogleAuthProvider(client_secret="test-secret-key")

    # 1. Valid token
    state = provider.generate_state()
    assert provider.verify_state(state) is True

    # 2. Tampered token
    tampered_state = state[:-2] + "xx"
    assert provider.verify_state(tampered_state) is False

    # 3. Expired token (max_age_seconds=0 should immediately expire)
    assert provider.verify_state(state, max_age_seconds=-1) is False

    # 4. Invalid / empty formats
    assert provider.verify_state("") is False
    assert provider.verify_state(None) is False
    assert provider.verify_state("invalid-base64-content!") is False
    assert provider.verify_state("bm90LWEtdmFsaWQtdG9rZW4=") is False
