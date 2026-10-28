"""MCP servers in front of the source systems a proof of value reads (MCP v2, streamable HTTP).

Each server is a resource server: it accepts only approval tokens issued by the desk for its URL,
and checks on every call that the tool is approved and that nothing above the approved data
ceiling leaves it. The agent's own tool filter is a second, client-side line.
"""

from __future__ import annotations

import itertools
import json
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import uvicorn
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import AnyHttpUrl

from desk import settings, tokens
from desk.pov.corpus import index

_tickets = itertools.count(1)


class ScopeViolation(ToolError):
    """Reported to the client as a tool error with this message (not a generic failure)."""

    pass


@dataclass
class ServerLog:
    calls: list[dict[str, Any]] = field(default_factory=list)
    refused: list[dict[str, Any]] = field(default_factory=list)
    handovers: list[dict[str, Any]] = field(default_factory=list)


class ApprovalTokenVerifier:
    def __init__(self, audience: str):
        self.audience = audience

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            claims = tokens.verify(token, self.audience)
        except Exception:
            return None
        return AccessToken(
            token=token,
            client_id=str(claims["sub"]),
            scopes=list(claims["tools"]),
            expires_at=int(claims["exp"]),
            resource=self.audience,
            subject=str(claims["sub"]),
            claims=claims,
        )


def _claims() -> dict[str, Any]:
    tok = get_access_token()
    if tok is None or tok.claims is None:
        raise ScopeViolation("no approval token")
    return tok.claims


def _require(tool: str, log: ServerLog) -> dict[str, Any]:
    c = _claims()
    if tool not in c["tools"]:
        log.refused.append({"tool": tool, "approval": c["sub"], "reason": "tool not approved"})
        raise ScopeViolation(f"{tool} is not in approval {c['sub']}")
    return c


def records_server(corpus: str, url: str, log: ServerLog) -> MCPServer[Any]:
    """Read-only tools over a corpus, with the data ceiling enforced here, not in the agent."""
    ix = index(corpus)
    # The verifier checks the audience itself (tokens.verify), so the middleware need not.
    auth = AuthSettings(
        issuer_url=AnyHttpUrl(f"https://desk.invalid/{tokens.ISSUER}"),
        resource_server_url=AnyHttpUrl(url),
        validate_token_resource=False,
    )
    srv: MCPServer[Any] = MCPServer(
        name=f"{corpus}-records",
        instructions="Read-only access to approved documents. Every passage has a citable id.",
        auth=auth,
        token_verifier=ApprovalTokenVerifier(url),
    )

    def search(tool: str, query: str) -> str:
        c = _require(tool, log)
        ceiling = int(c["ceiling"])
        cfg = settings.load("pov")["retrieval"]
        hits = ix.search(query, k=int(cfg["k"]), max_rank=ceiling)
        floor = float(cfg["answer_floor"])
        min_cov = float(cfg["min_coverage"])
        above = [
            p
            for p, s in ix.search(query, k=int(cfg["k"]))
            if settings.class_rank(p.classification) > ceiling and s >= floor and ix.coverage(query, {p.doc}) >= min_cov
        ]
        withheld = len({p.doc for p in above})
        log.calls.append({"tool": tool, "query": query, "returned": [p.id for p, _ in hits], "withheld": withheld})
        out: dict[str, Any] = {
            "passages": [
                {"id": p.id, "title": p.title, "text": p.text, "unit": p.unit, "score": round(s, 3)} for p, s in hits
            ]
        }
        if tool == "search_records":
            out["withheld_documents"] = withheld
        return json.dumps(out, ensure_ascii=False)

    if corpus == "wohngeld":

        @srv.tool()
        def search_guidance(query: str) -> str:
            """Search the office's published Wohngeld guidance. Returns passages with ids like WG-03#2."""
            return search("search_guidance", query)

        @srv.tool()
        def get_contact() -> str:
            """Opening hours and how to reach the Wohngeld service."""
            _require("get_contact", log)
            d = ix.docs["WG-12"]
            log.calls.append({"tool": "get_contact", "returned": [p.id for p in d.passages]})
            return json.dumps(
                {"passages": [{"id": p.id, "title": p.title, "text": p.text} for p in d.passages]}, ensure_ascii=False
            )

        @srv.tool()
        def create_handover(reason: str, topic: str) -> str:
            """Hand the conversation to the Wohngeld team. Use for anything about the person's own case."""
            c = _require("create_handover", log)
            ticket = f"HO-{next(_tickets):05d}"
            log.handovers.append({"ticket": ticket, "reason": reason, "topic": topic, "approval": c["sub"]})
            return json.dumps({"ticket": ticket, "queue": "Wohngeldstelle"})

    else:

        @srv.tool()
        def search_records(query: str) -> str:
            """Search the ministry's records. Passages above the approved classification are withheld and only counted."""
            return search("search_records", query)

        @srv.tool()
        def get_record(record_id: str) -> str:
            """Read one record in full, if its classification is within the approval."""
            c = _require("get_record", log)
            d = ix.docs.get(record_id)
            if d is None:
                return json.dumps({"error": "unknown record"})
            if settings.class_rank(d.classification) > int(c["ceiling"]):
                log.refused.append(
                    {"tool": "get_record", "approval": c["sub"], "reason": "above ceiling", "record": record_id}
                )
                return json.dumps({"error": "above the approved classification"})
            log.calls.append({"tool": "get_record", "returned": [p.id for p in d.passages]})
            return json.dumps(
                {
                    "id": d.id,
                    "title": d.title,
                    "unit": d.unit,
                    "passages": [{"id": p.id, "text": p.text} for p in d.passages],
                },
                ensure_ascii=False,
            )

        @srv.tool()
        def export_all_records() -> str:
            """Bulk export (exists on the server, never approved: proves the server refuses it)."""
            _require("export_all_records", log)
            return json.dumps({"records": [d.id for d in ix.docs.values()]})

    return srv


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@dataclass
class Running:
    url: str
    log: ServerLog
    server: uvicorn.Server


_running: dict[str, Running] = {}
_lock = threading.Lock()


def serve(corpus: str) -> Running:
    """Start (once per process) an MCP server for a corpus on a free local port."""
    with _lock:
        if corpus in _running:
            return _running[corpus]
        port = free_port()
        url = f"http://127.0.0.1:{port}/mcp"
        log = ServerLog()
        app = records_server(corpus, url, log).streamable_http_app(stateless_http=True, json_response=True)
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
        threading.Thread(target=server.run, daemon=True).start()
        deadline = time.time() + 10
        while not server.started:
            if time.time() > deadline:
                raise RuntimeError(f"MCP server for {corpus} did not start")
            time.sleep(0.02)
        _running[corpus] = Running(url, log, server)
        return _running[corpus]
