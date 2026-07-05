"""Unit tests for auth crypto (no DB needed)."""

import jwt
import pytest

from src.api.security import create_token, decode_token, hash_password, verify_password


def test_password_hash_roundtrip():
    h = hash_password("s3cret-pass")
    assert h != "s3cret-pass"
    assert verify_password("s3cret-pass", h)
    assert not verify_password("wrong", h)


def test_verify_handles_bad_hash():
    assert verify_password("x", "not-a-bcrypt-hash") is False


def test_jwt_roundtrip_carries_claims():
    token = create_token("user@example.com", role="admin")
    claims = decode_token(token)
    assert claims["sub"] == "user@example.com"
    assert claims["role"] == "admin"


def test_jwt_rejects_garbage():
    with pytest.raises(jwt.PyJWTError):
        decode_token("not.a.jwt")


def test_jwt_rejects_expired():
    token = create_token("user@example.com", ttl=-1)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(token)
