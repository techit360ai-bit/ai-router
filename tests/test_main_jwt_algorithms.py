"""The router must verify the same token algorithms the platform issues.

Regression guard for the production 401: the Node backend mints RS256 tokens in
staging/production (HS256 is forbidden there), so a router that only accepted
HS256 rejected every authenticated browser call.
"""

from __future__ import annotations

import os
import sys

import pytest
from fastapi import HTTPException
from jose import jwt as jose_jwt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SECRET_KEY", "unit-test-secret-value-that-is-long-enough")
os.environ.setdefault("ENVIRONMENT", "development")

import main as main_module  # noqa: E402


def _rsa_keypair() -> tuple[str, str]:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_pem, public_pem


@pytest.fixture()
def rsa_keys() -> tuple[str, str]:
    return _rsa_keypair()


def test_hs256_token_uses_shared_secret(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "SECRET_KEY", "shared-hs256-secret")
    monkeypatch.setattr(main_module, "JWT_PUBLIC_KEY", None)
    monkeypatch.setattr(main_module, "JWT_ALLOWED_ALGORITHMS", frozenset({"HS256", "RS256"}))
    token = jose_jwt.encode({"sub": "u1"}, "shared-hs256-secret", algorithm="HS256")

    key, algorithms = main_module._jwt_verification_material(token)

    assert key == "shared-hs256-secret"
    assert algorithms == ["HS256"]


def test_rs256_token_prefers_public_key(monkeypatch, rsa_keys) -> None:
    private_pem, public_pem = rsa_keys
    monkeypatch.setattr(main_module, "SECRET_KEY", "shared-hs256-secret")
    monkeypatch.setattr(main_module, "JWT_PUBLIC_KEY", public_pem)
    monkeypatch.setattr(main_module, "JWT_ALLOWED_ALGORITHMS", frozenset({"HS256", "RS256"}))
    token = jose_jwt.encode({"sub": "u1"}, private_pem, algorithm="RS256")

    key, algorithms = main_module._jwt_verification_material(token)

    assert key == public_pem
    assert algorithms == ["RS256"]


def test_rs256_without_public_key_fails_closed(monkeypatch, rsa_keys) -> None:
    private_pem, _ = rsa_keys
    monkeypatch.setattr(main_module, "SECRET_KEY", "shared-hs256-secret")
    monkeypatch.setattr(main_module, "JWT_PUBLIC_KEY", None)
    monkeypatch.setattr(main_module, "JWT_ALLOWED_ALGORITHMS", frozenset({"HS256", "RS256"}))
    token = jose_jwt.encode({"sub": "u1"}, private_pem, algorithm="RS256")

    with pytest.raises(HTTPException) as excinfo:
        main_module._jwt_verification_material(token)

    assert excinfo.value.status_code == 500


def test_disallowed_algorithm_is_rejected(monkeypatch, rsa_keys) -> None:
    private_pem, public_pem = rsa_keys
    monkeypatch.setattr(main_module, "SECRET_KEY", "shared-hs256-secret")
    monkeypatch.setattr(main_module, "JWT_PUBLIC_KEY", public_pem)
    monkeypatch.setattr(main_module, "JWT_ALLOWED_ALGORITHMS", frozenset({"HS256"}))
    token = jose_jwt.encode({"sub": "u1"}, private_pem, algorithm="RS256")

    with pytest.raises(HTTPException) as excinfo:
        main_module._jwt_verification_material(token)

    assert excinfo.value.status_code == 401
