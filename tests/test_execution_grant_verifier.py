"""Execution-grant verifier must agree with the backend signer's key choice."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402
from jose import jwt  # noqa: E402

from execution_controls import ExecutionGrantVerifier  # noqa: E402


def _rsa_pair():
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


def _set_env(monkeypatch, **env):
    for key in ("ENVIRONMENT", "AI_EXECUTION_GRANT_ALGORITHM", "AI_EXECUTION_GRANT_SECRET",
                "AI_EXECUTION_GRANT_PUBLIC_KEY", "JWT_PUBLIC_KEY", "JWT_SECRET"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)


def test_rs256_verifies_with_jwt_public_key_even_when_a_shared_secret_is_set(monkeypatch):
    private_pem, public_pem = _rsa_pair()
    _set_env(
        monkeypatch,
        ENVIRONMENT="production",
        AI_EXECUTION_GRANT_SECRET="a-shared-hmac-secret-must-not-break-rs256",
        JWT_PUBLIC_KEY=public_pem,
    )
    verifier = ExecutionGrantVerifier()
    assert verifier.algorithm == "RS256"
    assert verifier.secret == public_pem

    token = jwt.encode(
        {"sub": "user-1", "request_id": "req-1", "task_type": "gsis_compute",
         "iss": "techit-backend", "aud": "techit-ai-router"},
        private_pem, algorithm="RS256",
    )
    grant = verifier.verify(token)
    assert grant.subject == "user-1"
    assert grant.task_type == "gsis_compute"


def test_hs256_dev_uses_the_shared_grant_secret(monkeypatch):
    _set_env(monkeypatch, ENVIRONMENT="development", AI_EXECUTION_GRANT_SECRET="dev-grant-secret")
    verifier = ExecutionGrantVerifier()
    assert verifier.algorithm == "HS256"
    assert verifier.secret == "dev-grant-secret"

    token = jwt.encode(
        {"sub": "user-2", "request_id": "req-2", "iss": "techit-backend", "aud": "techit-ai-router"},
        "dev-grant-secret", algorithm="HS256",
    )
    assert verifier.verify(token).subject == "user-2"
