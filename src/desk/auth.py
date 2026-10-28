"""Who is calling, and which customers they may see.

Production: tokens from the organisation's OpenID Connect provider (Keycloak, Entra ID…), verified
against its JWKS; the `desk_role` and `desk_customers` claims come from directory groups through a
claim mapper. Development and tests: `DESK_AUTH=dev` accepts tokens signed with the desk's own key,
minted by `desk token`. Visibility is enforced again in PostgreSQL (row-level security).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import cache
from typing import Any

import httpx
import jwt

from desk import tokens

ROLES = ("architect", "specialist", "customer")
DEV_ISSUER = "desk-dev"
DEV_AUDIENCE = "desk-api"


class Unauthorized(Exception):
    pass


@dataclass(frozen=True)
class Principal:
    subject: str
    role: str
    customers: tuple[str, ...]

    @property
    def can_write(self) -> bool:
        return self.role == "architect"


def mint_dev(subject: str, role: str, customers: list[str], ttl: int = 3600) -> str:
    import time

    now = int(time.time())
    return jwt.encode(
        {
            "iss": DEV_ISSUER,
            "aud": DEV_AUDIENCE,
            "sub": subject,
            "desk_role": role,
            "desk_customers": customers,
            "iat": now,
            "exp": now + ttl,
        },
        tokens._private_key(),
        algorithm="EdDSA",
    )


@cache
def _jwks_client(issuer: str) -> jwt.PyJWKClient:
    conf = httpx.get(issuer.rstrip("/") + "/.well-known/openid-configuration", timeout=5).json()
    return jwt.PyJWKClient(conf["jwks_uri"])


def _claims_from(raw: dict[str, Any]) -> Principal:
    role = raw.get("desk_role")
    customers = raw.get("desk_customers") or []
    if isinstance(customers, str):
        customers = [c for c in customers.replace(" ", ",").split(",") if c]
    if role not in ROLES:
        raise Unauthorized("token carries no desk role")
    if not customers:
        raise Unauthorized("token names no customers")
    return Principal(str(raw.get("sub")), str(role), tuple(sorted(set(customers))))


def verify(token: str) -> Principal:
    mode = os.environ.get("DESK_AUTH", "oidc")
    try:
        if mode == "dev":
            raw = jwt.decode(token, tokens.public_key(), algorithms=["EdDSA"], audience=DEV_AUDIENCE, issuer=DEV_ISSUER)
        else:
            issuer = os.environ["DESK_OIDC_ISSUER"]
            audience = os.environ.get("DESK_OIDC_AUDIENCE", "desk-api")
            key = _jwks_client(issuer).get_signing_key_from_jwt(token)
            raw = jwt.decode(token, key.key, algorithms=["RS256", "ES256", "EdDSA"], audience=audience, issuer=issuer)
    except (jwt.PyJWTError, KeyError, httpx.HTTPError) as e:
        raise Unauthorized(str(e)) from e
    return _claims_from(raw)
