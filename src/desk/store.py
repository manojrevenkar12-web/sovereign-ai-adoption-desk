"""PostgreSQL record of the desk: read side under row-level security, compute side for the planner.

Requests run `SET LOCAL ROLE desk_app` with `desk.customers` set from the caller's token, so a
query that forgets a WHERE clause still cannot read another customer's rows. The planner runs as
desk_planner, recomputes the whole portfolio (reviewer and Deployment Engineering capacity is
shared across customers) and materialises one plan row per use case and one view per customer.
Events are append-only (a trigger refuses UPDATE and DELETE) and hash-chained per customer.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from desk import settings
from desk.adoption import WeekRow, health
from desk.analysis import analyse
from desk.approval import Approval, problems
from desk.approval import load as load_approval
from desk.model import Customer, check_unique, customer_from, raw_portfolio

MIGRATIONS = settings.ROOT / "migrations"


def _json(v: Any) -> Any:
    return json.loads(json.dumps(v, default=lambda o: o.isoformat() if isinstance(o, date) else str(o)))


class Store:
    def __init__(self, dsn: str):
        self.dsn = dsn

    def connect(self) -> psycopg.Connection[dict[str, Any]]:
        return psycopg.connect(self.dsn, row_factory=dict_row)

    # ------------------------------------------------------------------ schema and seed

    def migrate(self) -> list[str]:
        applied = []
        with self.connect() as conn:
            exists = conn.execute("SELECT to_regclass('schema_migrations') AS t").fetchone()
            done = set()
            if exists and exists["t"]:
                done = {r["version"] for r in conn.execute("SELECT version FROM schema_migrations")}
            for f in sorted(MIGRATIONS.glob("*.sql")):
                if f.stem in done:
                    continue
                conn.execute(f.read_text())  # type: ignore[arg-type]
                conn.execute("INSERT INTO schema_migrations(version) VALUES (%s)", (f.stem,))
                applied.append(f.stem)
        return applied

    def seed(self, data_dir: Path | None = None) -> dict[str, int]:
        d = data_dir or settings.DATA_DIR
        raws = raw_portfolio(d / "portfolio")
        check_unique([customer_from(r) for r in raws])
        counts = {"customers": 0, "use_cases": 0, "approvals": 0, "usage": 0}
        with self.connect() as conn, conn.transaction():
            conn.execute("SET LOCAL ROLE desk_planner")
            for r in raws:
                doc = _json({k: v for k, v in r.items() if k != "use_cases"})
                conn.execute(
                    "INSERT INTO customers(id, doc) VALUES (%s, %s) ON CONFLICT (id) DO UPDATE SET doc = EXCLUDED.doc",
                    (r["id"], Jsonb(doc)),
                )
                counts["customers"] += 1
                for u in r.get("use_cases", []) or []:
                    conn.execute(
                        "INSERT INTO use_cases(id, customer_id, doc) VALUES (%s, %s, %s) "
                        "ON CONFLICT (id) DO UPDATE SET doc = EXCLUDED.doc",
                        (u["id"], r["id"], Jsonb(_json(u))),
                    )
                    counts["use_cases"] += 1
            owner = {u["id"]: r["id"] for r in raws for u in r.get("use_cases", []) or []}
            for f in sorted((d / "approvals").glob("*.yaml")):
                a = load_approval(f)
                conn.execute(
                    "INSERT INTO approvals(id, use_case_id, customer_id, doc) VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (id) DO UPDATE SET doc = EXCLUDED.doc",
                    (a.id, a.use_case, owner[a.use_case], Jsonb(_json(a.as_dict()))),
                )
                counts["approvals"] += 1
            for f in sorted((d / "usage").glob("*.csv")):
                cid = f.stem
                with f.open(encoding="utf-8") as fh:
                    rows = [
                        (
                            cid,
                            r["week"],
                            r["department"],
                            int(r["seats"]),
                            int(r["weekly_active_users"]),
                            int(r["messages"]),
                        )
                        for r in csv.DictReader(fh)
                    ]
                with conn.cursor() as cur:
                    cur.executemany("INSERT INTO usage_weekly VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING", rows)
                counts["usage"] += len(rows)
        return counts

    # ------------------------------------------------------------------ planner (compute side)

    def _load(
        self, conn: psycopg.Connection[dict[str, Any]]
    ) -> tuple[list[Customer], dict[str, Approval], dict[str, list[WeekRow]]]:
        customers = []
        for c in conn.execute("SELECT id, doc FROM customers ORDER BY id"):
            ucs = conn.execute("SELECT doc FROM use_cases WHERE customer_id = %s ORDER BY id", (c["id"],)).fetchall()
            customers.append(customer_from({**c["doc"], "use_cases": [u["doc"] for u in ucs]}))
        approvals = {}
        for a in conn.execute("SELECT doc FROM approvals"):
            doc = dict(a["doc"])
            for k in ("approved_by", "request_classes", "tools", "forbidden"):
                doc[k] = tuple(doc.get(k) or ())
            for k in ("approved_on", "valid_until"):
                doc[k] = date.fromisoformat(doc[k])
            approvals[doc["use_case"]] = Approval(**doc)
        usage: dict[str, list[WeekRow]] = {}
        for r in conn.execute("SELECT * FROM usage_weekly ORDER BY week, department"):
            usage.setdefault(r["customer_id"], []).append(
                WeekRow(r["week"], r["department"], r["seats"], r["active"], r["messages"])
            )
        return customers, approvals, usage

    def replan(self, today: date) -> dict[str, Any]:
        """Recompute the portfolio and materialise it. Runs as desk_planner."""
        with self.connect() as conn, conn.transaction():
            conn.execute("SET LOCAL ROLE desk_planner")
            conn.execute("SELECT pg_advisory_xact_lock(4711)")
            customers, approvals, usage = self._load(conn)
            a = analyse(customers, today)
            now = datetime.now(UTC)
            conn.execute("DELETE FROM plans")
            conn.execute("DELETE FROM customer_views")
            prio = {p.use_case: p for p in a.priorities}
            rank = {p.use_case: i + 1 for i, p in enumerate(a.priorities)}
            plan = a.plan.as_dict()
            for c in customers:
                for u in c.use_cases:
                    cl = a.classifications[u.id]
                    ap = approvals.get(u.id)
                    doc = {
                        "useCase": _json(asdict(u)),
                        "classification": cl.as_dict(),
                        "priority": prio[u.id].as_dict() if u.id in prio else None,
                        "rank": rank.get(u.id),
                        "path": plan["useCases"].get(u.id),
                        "architecture": a.architectures[u.id].as_dict() if u.id in a.architectures else None,
                        "approval": ({**_json(ap.as_dict()), "problems": problems(ap, cl, today)} if ap else None),
                    }
                    conn.execute("INSERT INTO plans VALUES (%s, %s, %s, %s)", (u.id, c.id, now, Jsonb(doc)))
                ids = {u.id for u in c.use_cases}
                h = health(c, usage.get(c.id, []), approvals, today)
                view = {
                    "customer": _json({k: v for k, v in asdict(c).items() if k != "use_cases"}),
                    "health": h.as_dict(),
                    "bottlenecks": [b for b in plan["bottlenecks"] if b["customer"] in (c.id, "portfolio")],
                    "levers": [
                        {
                            **lv,
                            "useCases": {k: v for k, v in lv["useCases"].items() if k in ids},
                            "weeksSaved": sum(v for k, v in lv["useCases"].items() if k in ids),
                        }
                        for lv in a.levers
                        if ids & set(lv["useCases"])
                    ],
                    "planStart": plan["start"],
                }
                conn.execute("INSERT INTO customer_views VALUES (%s, %s, %s)", (c.id, now, Jsonb(view)))
        return {"useCases": sum(len(c.use_cases) for c in customers), "customers": len(customers)}

    # ------------------------------------------------------------------ read side (RLS)

    @contextmanager
    def scoped(self, customers: list[str]) -> Iterator[psycopg.Connection[dict[str, Any]]]:
        with self.connect() as conn, conn.transaction():
            conn.execute("SET LOCAL ROLE desk_app")
            conn.execute("SELECT set_config('desk.customers', %s, true)", (",".join(customers),))
            yield conn

    def portfolio(self, customers: list[str]) -> dict[str, Any]:
        with self.scoped(customers) as conn:
            views = conn.execute(
                "SELECT customer_id, computed_at, doc FROM customer_views ORDER BY customer_id"
            ).fetchall()
            plans = conn.execute("SELECT use_case_id, customer_id, doc FROM plans").fetchall()
        by_c: dict[str, list[dict[str, Any]]] = {}
        for p in plans:
            by_c.setdefault(p["customer_id"], []).append(p["doc"])
        out = []
        for v in views:
            ucs = sorted(by_c.get(v["customer_id"], []), key=lambda d: (d["rank"] or 999, d["useCase"]["id"]))
            out.append({**v["doc"], "computedAt": v["computed_at"].isoformat(), "useCases": [_summary(d) for d in ucs]})
        return {"customers": out}

    def dossier(self, customers: list[str], use_case: str) -> dict[str, Any] | None:
        with self.scoped(customers) as conn:
            row = conn.execute("SELECT doc FROM plans WHERE use_case_id = %s", (use_case,)).fetchone()
            runs = conn.execute(
                "SELECT at, doc FROM pov_runs WHERE use_case_id = %s ORDER BY id DESC LIMIT 5", (use_case,)
            ).fetchall()
        if row is None:
            return None
        return {**row["doc"], "povRuns": [{"at": r["at"].isoformat(), **r["doc"]} for r in runs]}

    def customer_view(self, customers: list[str], customer: str) -> dict[str, Any] | None:
        with self.scoped(customers) as conn:
            row = conn.execute("SELECT doc FROM customer_views WHERE customer_id = %s", (customer,)).fetchone()
            plans = conn.execute("SELECT doc FROM plans WHERE customer_id = %s", (customer,)).fetchall()
        if row is None:
            return None
        return {**row["doc"], "plans": [p["doc"] for p in plans]}

    # ------------------------------------------------------------------ writes

    def append_event(
        self, conn: psycopg.Connection[dict[str, Any]], customer: str, actor: str, kind: str, payload: dict[str, Any]
    ) -> str:
        conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (customer,))
        prev = conn.execute(
            "SELECT hash FROM events WHERE customer_id = %s ORDER BY id DESC LIMIT 1", (customer,)
        ).fetchone()
        prev_hash = prev["hash"] if prev else None
        body = json.dumps(
            {"customer": customer, "actor": actor, "kind": kind, "payload": payload, "prev": prev_hash},
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        )
        h = hashlib.sha256(body.encode()).hexdigest()
        conn.execute(
            "INSERT INTO events(customer_id, actor, kind, payload, prev_hash, hash) VALUES (%s,%s,%s,%s,%s,%s)",
            (customer, actor, kind, Jsonb(_json(payload)), prev_hash, h),
        )
        return h

    def events(self, customers: list[str], customer: str) -> dict[str, Any]:
        with self.scoped(customers) as conn:
            rows = conn.execute("SELECT * FROM events WHERE customer_id = %s ORDER BY id", (customer,)).fetchall()
        prev, intact = None, True
        for r in rows:
            body = json.dumps(
                {
                    "customer": r["customer_id"],
                    "actor": r["actor"],
                    "kind": r["kind"],
                    "payload": r["payload"],
                    "prev": prev,
                },
                sort_keys=True,
                ensure_ascii=False,
                default=str,
            )
            if r["prev_hash"] != prev or hashlib.sha256(body.encode()).hexdigest() != r["hash"]:
                intact = False
            prev = r["hash"]
        return {
            "intact": intact,
            "events": [
                {
                    "at": r["at"].isoformat(),
                    "actor": r["actor"],
                    "kind": r["kind"],
                    "payload": r["payload"],
                    "hash": r["hash"][:12],
                }
                for r in rows
            ],
        }

    def update_use_case(
        self, customers: list[str], actor: str, use_case: str, change: dict[str, Any], kind: str
    ) -> dict[str, Any] | None:
        """Change a use case's doc as the caller (RLS applies) and record the event in the same transaction."""
        with self.scoped(customers) as conn:
            row = conn.execute(
                "SELECT customer_id, doc FROM use_cases WHERE id = %s FOR UPDATE", (use_case,)
            ).fetchone()
            if row is None:
                return None
            doc = {**row["doc"], **change}
            conn.execute("UPDATE use_cases SET doc = %s WHERE id = %s", (Jsonb(doc), use_case))
            self.append_event(conn, row["customer_id"], actor, kind, {"useCase": use_case, **change})
        return doc

    def record_pov_run(
        self, customers: list[str], actor: str, customer: str, use_case: str, doc: dict[str, Any]
    ) -> None:
        with self.scoped(customers) as conn:
            conn.execute(
                "INSERT INTO pov_runs(customer_id, use_case_id, doc) VALUES (%s, %s, %s)",
                (customer, use_case, Jsonb(_json(doc))),
            )
            self.append_event(conn, customer, actor, "pov_run", {"useCase": use_case, "action": doc.get("action")})


def _summary(d: dict[str, Any]) -> dict[str, Any]:
    u, cl, path = d["useCase"], d["classification"], d.get("path") or {}
    return {
        "id": u["id"],
        "title": u["title"],
        "stage": u["stage"],
        "pattern": u["pattern"],
        "aiActClass": cl["aiAct"]["class"],
        "stops": cl["stops"],
        "rank": d.get("rank"),
        "priority": d.get("priority"),
        "goLive": path.get("goLive"),
        "readyBy": path.get("readyBy"),
        "waitingFor": path.get("waitingFor"),
        "blockers": len(u.get("blockers") or []),
        "gates": [
            {
                "gate": g["gate"],
                "startWeek": g["startWeek"],
                "endWeek": g["endWeek"],
                "done": g["done"],
                "wait": g["wait"],
                "waitedWeeks": g["waitedWeeks"],
            }
            for g in path.get("gates", [])
        ],
        "critical": path.get("critical", []),
    }
