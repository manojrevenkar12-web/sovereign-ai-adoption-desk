"""PostgreSQL record and HTTP API: row-level security, append-only events, write rules."""

from __future__ import annotations

import os
import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

from desk.auth import mint_dev
from desk.store import Store

from .conftest import TODAY

pytestmark = pytest.mark.db


@pytest.fixture(scope="module")
def store(dsn: str) -> Store:  # type: ignore[misc]
    name = f"desk_test_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(dsn, autocommit=True) as c:
        c.execute(f'CREATE DATABASE "{name}"')
    url = dsn.rsplit("/", 1)[0] + f"/{name}"
    st = Store(url)
    st.migrate()
    st.seed()
    st.replan(TODAY)
    yield st
    with psycopg.connect(dsn, autocommit=True) as c:
        c.execute(f'DROP DATABASE "{name}" WITH (FORCE)')


@pytest.fixture(scope="module")
def client(store: Store):  # type: ignore[no-untyped-def]
    os.environ["DESK_AUTH"] = "dev"
    os.environ["DESK_TODAY"] = TODAY.isoformat()
    from desk.api import create_app

    with TestClient(create_app(store)) as c:
        yield c


def h(role: str = "architect", customers: str = "lws,stmv,lechfeld,bafm") -> dict[str, str]:
    return {"Authorization": f"Bearer {mint_dev('t@example.org', role, customers.split(','))}"}


def test_rls_scopes_every_read(store: Store) -> None:
    assert [c["customer"]["id"] for c in store.portfolio(["lws"])["customers"]] == ["lws"]
    assert store.dossier(["stmv"], "lws-wohngeld-auskunft") is None
    with store.scoped(["stmv"]) as conn:  # a query without any WHERE still sees one customer
        ids = {r["customer_id"] for r in conn.execute("SELECT customer_id FROM plans")}
    assert ids == {"stmv"}


def test_rls_refuses_writes_into_another_customer(store: Store) -> None:
    with pytest.raises(psycopg.Error), store.scoped(["stmv"]) as conn:
        conn.execute(
            "INSERT INTO pov_runs(customer_id, use_case_id, doc) VALUES ('lws', 'lws-wohngeld-auskunft', '{}')"
        )


def test_events_are_append_only_and_chained(store: Store) -> None:
    store.update_use_case(["lws"], "a", "lws-bescheid-erlaeuterung", {"stage": "qualified"}, "stage_changed")
    store.update_use_case(["lws"], "a", "lws-bescheid-erlaeuterung", {"stage": "discovery"}, "stage_changed")
    ev = store.events(["lws"], "lws")
    assert ev["intact"] and len(ev["events"]) >= 2
    with pytest.raises(psycopg.Error), store.connect() as conn:
        conn.execute("UPDATE events SET actor = 'someone else'")


def test_replan_materialises_every_use_case(store: Store) -> None:
    with store.scoped(["lws", "stmv", "lechfeld", "bafm"]) as conn:
        n = conn.execute("SELECT count(*) AS n FROM plans").fetchone()
    assert n is not None and n["n"] == 16


def test_api_requires_a_valid_token(client: TestClient) -> None:
    assert client.get("/api/portfolio").status_code == 401
    assert client.get("/api/portfolio", headers={"Authorization": "Bearer nonsense"}).status_code == 401


def test_customer_sees_only_itself(client: TestClient) -> None:
    r = client.get("/api/portfolio", headers=h("customer", "lws"))
    assert [c["customer"]["id"] for c in r.json()["customers"]] == ["lws"]
    assert client.get("/api/use-cases/stmv-kleine-anfragen", headers=h("customer", "lws")).status_code == 404


def test_only_the_architect_writes(client: TestClient) -> None:
    r = client.post(
        "/api/use-cases/lws-wohngeld-auskunft/gates/legal_basis", json={"done": True}, headers=h("specialist")
    )
    assert r.status_code == 403


def test_production_needs_every_gate_and_an_approval(client: TestClient) -> None:
    r = client.post("/api/use-cases/stmv-codex-fachverfahren/stage", json={"stage": "proof_of_value"}, headers=h())
    assert r.status_code == 200
    r = client.post("/api/use-cases/stmv-codex-fachverfahren/stage", json={"stage": "production"}, headers=h())
    assert r.status_code == 409
    reasons = " ".join(r.json()["detail"]["reasons"])
    assert "one stage at a time" in reasons and "no approval record" in reasons


def test_stopped_use_case_cannot_advance(client: TestClient) -> None:
    r = client.post("/api/use-cases/bafm-hotline-stimmung/stage", json={"stage": "discovery"}, headers=h())
    assert r.status_code == 409 and "stopped" in r.text


def test_passing_a_gate_replans(client: TestClient) -> None:
    before = client.get("/api/use-cases/lechfeld-bauantrag", headers=h()).json()["path"]["goLive"]
    r = client.post("/api/use-cases/lechfeld-bauantrag/gates/security_concept", json={"done": True}, headers=h())
    assert r.status_code == 200
    assert r.json()["path"]["goLive"] <= before
    assert "security_concept" in r.json()["useCase"]["done"]


def test_proof_of_value_runs_through_the_approval(client: TestClient) -> None:
    r = client.post(
        "/api/use-cases/lws-wohngeld-auskunft/pov",
        json={"message": "Wann ist die Servicestelle erreichbar?"},
        headers=h(),
    )
    assert r.status_code == 200 and r.json()["action"] == "answer"
    runs = client.get("/api/use-cases/lws-wohngeld-auskunft", headers=h()).json()["povRuns"]
    assert runs and runs[0]["kind"] == "wohngeld"
    assert client.post("/api/use-cases/lechfeld-bauantrag/pov", json={"message": "x"}, headers=h()).status_code == 409


def test_account_plan_and_mcp(client: TestClient) -> None:
    md = client.get("/api/customers/bafm/plan.md", headers=h()).text
    assert md.startswith("# Technical account plan") and "Decisions needed" in md
    assert client.get("/metrics").text.count("desk_") >= 1


@pytest.fixture(scope="module")
def live_api(store: Store):  # type: ignore[no-untyped-def]
    """The API with its MCP server, on a real port: MCP needs streamable HTTP, not the test client."""
    import threading
    import time

    import uvicorn

    from desk.api import create_app
    from desk.pov.servers import free_port

    os.environ["DESK_AUTH"] = "dev"
    port = free_port()
    server = uvicorn.Server(uvicorn.Config(create_app(store), host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.02)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True


async def test_desk_mcp_answers_within_the_token_scope(live_api: str) -> None:
    import json

    from agents.mcp import MCPServerStreamableHttp

    params = {"url": f"{live_api}/mcp-server/mcp", "headers": h("customer", "lws")}
    async with MCPServerStreamableHttp(params=params) as s:  # type: ignore[arg-type]
        assert {t.name for t in await s.list_tools()} == {
            "portfolio_status",
            "use_case_dossier",
            "whats_blocking",
            "account_health",
        }
        status = json.loads((await s.call_tool("portfolio_status", {})).content[0].text)  # type: ignore[union-attr]
        assert [c["customer"] for c in status] == ["Landesamt für Wohnen und Soziales (fictional)"]
        other = json.loads((await s.call_tool("account_health", {"customer_id": "stmv"})).content[0].text)  # type: ignore[union-attr]
        assert other == {"error": "not in your portfolio"}


async def test_desk_mcp_refuses_without_a_valid_token(live_api: str) -> None:
    from agents.mcp import MCPServerStreamableHttp

    params = {"url": f"{live_api}/mcp-server/mcp", "headers": {"Authorization": "Bearer forged"}}
    with pytest.raises(BaseException):  # noqa: B017 - the MCP client raises an ExceptionGroup on 401
        async with MCPServerStreamableHttp(params=params) as s:  # type: ignore[arg-type]
            await s.list_tools()
