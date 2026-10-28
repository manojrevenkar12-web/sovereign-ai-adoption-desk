"""The desk as an MCP server, so the architect can ask from ChatGPT (developer-mode connectors) or Codex.

Same tokens as the API (OpenID Connect, or dev tokens in development) and the same row-level
security: a tool only ever sees the customers the caller's token names. Tools are read-only.
"""

from __future__ import annotations

import json
import os
from contextlib import AbstractAsyncContextManager
from typing import Any

from fastapi import FastAPI
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from pydantic import AnyHttpUrl
from starlette.applications import Starlette

from desk.auth import Unauthorized, verify
from desk.store import Store

PATH = "/mcp-server"


class DeskTokenVerifier:
    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            p = verify(token)
        except Unauthorized:
            return None
        return AccessToken(
            token=token,
            client_id=p.subject,
            scopes=[p.role],
            subject=p.subject,
            claims={"role": p.role, "customers": list(p.customers)},
        )


def _customers() -> list[str]:
    tok = get_access_token()
    if tok is None or not tok.claims:
        raise PermissionError("no token")
    return list(tok.claims["customers"])


def build(store: Store) -> tuple[Starlette, MCPServer[Any]]:
    public = os.environ.get("DESK_PUBLIC_URL", "http://localhost:8080")
    srv: MCPServer[Any] = MCPServer(
        name="sovereign-ai-adoption-desk",
        instructions=(
            "Read-only access to the AI architect's portfolio of public-sector customers: path to production, "
            "blockers, account health. Answer from tool results only."
        ),
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(os.environ.get("DESK_OIDC_ISSUER", "https://desk.invalid/dev")),
            resource_server_url=AnyHttpUrl(f"{public}{PATH}/mcp"),
            validate_token_resource=False,
        ),
        token_verifier=DeskTokenVerifier(),
    )

    @srv.tool()
    def portfolio_status() -> str:
        """Every customer in your portfolio with health and each use case's stage, AI Act class and go-live."""
        p = store.portfolio(_customers())
        out = []
        for c in p["customers"]:
            out.append(
                {
                    "customer": c["customer"]["name"],
                    "health": {"score": c["health"]["score"], "band": c["health"]["band"]},
                    "useCases": [
                        {k: u[k] for k in ("id", "title", "stage", "aiActClass", "goLive", "readyBy", "waitingFor")}
                        for u in c["useCases"]
                    ],
                }
            )
        return json.dumps(out, ensure_ascii=False)

    @srv.tool()
    def use_case_dossier(use_case_id: str) -> str:
        """Classification with sources, gates with dates, critical path and architecture of one use case."""
        d = store.dossier(_customers(), use_case_id)
        if d is None:
            return json.dumps({"error": "not in your portfolio"})
        return json.dumps(
            {k: d.get(k) for k in ("useCase", "classification", "path", "architecture", "approval")},
            ensure_ascii=False,
            default=str,
        )

    @srv.tool()
    def whats_blocking(customer_id: str) -> str:
        """What delays a customer's use cases: aged blockers, critical-path waits, and priced levers."""
        v = store.customer_view(_customers(), customer_id)
        if v is None:
            return json.dumps({"error": "not in your portfolio"})
        blockers = [
            {"useCase": d["useCase"]["id"], **b} for d in v["plans"] for b in d["useCase"].get("blockers") or []
        ]
        return json.dumps(
            {"blockers": blockers, "bottlenecks": v["bottlenecks"], "levers": v["levers"][:5]},
            ensure_ascii=False,
            default=str,
        )

    @srv.tool()
    def account_health(customer_id: str) -> str:
        """Adoption, momentum, departments and the interventions due, with the team that executes each."""
        v = store.customer_view(_customers(), customer_id)
        if v is None:
            return json.dumps({"error": "not in your portfolio"})
        return json.dumps(v["health"], ensure_ascii=False)

    return srv.streamable_http_app(streamable_http_path="/mcp", stateless_http=True, json_response=True), srv


def mount(app: FastAPI, store: Store) -> None:
    sub, _ = build(store)
    app.mount(PATH, sub)
    previous = app.router.lifespan_context

    def lifespan(a: FastAPI) -> AbstractAsyncContextManager[Any]:
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def run() -> Any:
            async with sub.router.lifespan_context(sub), previous(a):
                yield

        return run()

    app.router.lifespan_context = lifespan
