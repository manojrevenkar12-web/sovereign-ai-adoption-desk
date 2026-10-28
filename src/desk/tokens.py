"""Approval tokens: short-lived JWTs the desk issues so an MCP server can enforce an approval itself.

The agent presents the token on every MCP request. The server checks signature, audience and expiry,
and reads the approved tools and data ceiling from the claims, so a misconfigured or manipulated
client cannot widen the scope.
"""

from __future__ import annotations

import os
import time
from functools import cache
from pathlib import Path
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

ISSUER = "sovereign-ai-adoption-desk"


@cache
def _private_key() -> Ed25519PrivateKey:
    path = os.environ.get("DESK_SIGNING_KEY")
    if path and Path(path).exists():
        key = serialization.load_pem_private_key(Path(path).read_bytes(), password=None)
        assert isinstance(key, Ed25519PrivateKey)
        return key
    return Ed25519PrivateKey.generate()  # per process: fine for tests and a single-node pilot


def public_key() -> Ed25519PublicKey:
    return _private_key().public_key()


def issue(
    audience: str,
    approval: str,
    use_case: str,
    tools: tuple[str, ...],
    ceiling_rank: int,
    ttl_seconds: int = 900,
    expires_at: int | None = None,
) -> str:
    now = int(time.time())
    exp = now + ttl_seconds
    if expires_at is not None:
        exp = min(exp, expires_at)
    claims: dict[str, Any] = {
        "iss": ISSUER,
        "aud": audience,
        "sub": approval,
        "use_case": use_case,
        "tools": list(tools),
        "ceiling": ceiling_rank,
        "iat": now,
        "exp": exp,
    }
    return jwt.encode(claims, _private_key(), algorithm="EdDSA")


def verify(token: str, audience: str) -> dict[str, Any]:
    return jwt.decode(token, public_key(), algorithms=["EdDSA"], audience=audience, issuer=ISSUER)
