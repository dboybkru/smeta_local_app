from datetime import timedelta

import pytest

from app.core.security import (
    InvalidTokenError,
    _create_token,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip():
    h = hash_password("secret123")
    assert h != "secret123"
    assert verify_password("secret123", h)
    assert not verify_password("wrong", h)


def test_access_token_roundtrip():
    token = create_access_token(user_id=7, role="admin")
    payload = decode_token(token, expected_type="access")
    assert payload["sub"] == "7"
    assert payload["role"] == "admin"


def test_refresh_token_type_enforced():
    token = create_refresh_token(user_id=7, role="admin")
    with pytest.raises(InvalidTokenError):
        decode_token(token, expected_type="access")


def test_garbage_token_rejected():
    with pytest.raises(InvalidTokenError):
        decode_token("garbage", expected_type="access")


def test_corrupted_hash_returns_false():
    assert not verify_password("secret123", "not-a-valid-argon2-hash")


def test_expired_token_rejected():
    token = _create_token(1, "admin", "access", timedelta(seconds=-1))
    with pytest.raises(InvalidTokenError):
        decode_token(token, expected_type="access")
