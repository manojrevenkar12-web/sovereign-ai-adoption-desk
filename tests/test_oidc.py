"""Real OpenID Connect: tokens from Keycloak, verified against its JWKS (CI starts Keycloak)."""

from __future__ import annotations

import os

import httpx
import pytest

from desk.auth import Unauthorized, verify

pytestmark = pytest.mark.oidc

SECRETS = {
    "desk-architect": "architect-secret-for-ci-only",
    "desk-customer-lws": "customer-secret-for-ci-only",
    "desk-wrong-audience": "wrong-secret-for-ci-only",
}


@pytest.fixture(scope="module")
def issuer() -> str:
    url = os.environ.get("DESK_TEST_OIDC_ISSUER")
    if not url:
        pytest.skip("DESK_TEST_OIDC_ISSUER not set")
    os.environ.update({"DESK_AUTH": "oidc", "DESK_OIDC_ISSUER": url, "DESK_OIDC_AUDIENCE": "desk-api"})
    return url


def token(issuer: str, client: str) -> str:
    r = httpx.post(
        f"{issuer}/protocol/openid-connect/token",
        data={"grant_type": "client_credentials", "client_id": client, "client_secret": SECRETS[client]},
    )
    r.raise_for_status()
    return str(r.json()["access_token"])


def test_architect_token_from_keycloak(issuer: str) -> None:
    p = verify(token(issuer, "desk-architect"))
    assert p.role == "architect" and p.customers == ("bafm", "lechfeld", "lws", "stmv")


def test_customer_token_is_scoped(issuer: str) -> None:
    p = verify(token(issuer, "desk-customer-lws"))
    assert (p.role, p.customers, p.can_write) == ("customer", ("lws",), False)


def test_token_for_another_audience_is_refused(issuer: str) -> None:
    with pytest.raises(Unauthorized):
        verify(token(issuer, "desk-wrong-audience"))


def test_tampered_token_is_refused(issuer: str) -> None:
    t = token(issuer, "desk-customer-lws")
    head, body, sig = t.split(".")
    with pytest.raises(Unauthorized):
        verify(f"{head}.{body}.{sig[:-4]}AAAA")
