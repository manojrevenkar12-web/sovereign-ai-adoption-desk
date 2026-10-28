"""desk: take public-sector AI use cases from discovery to production."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import date
from pathlib import Path

for noisy in ("httpx", "httpx2", "mcp"):
    logging.getLogger(noisy).setLevel(logging.WARNING)


def _today(s: str | None) -> date:
    return date.fromisoformat(s) if s else date.fromisoformat(os.environ.get("DESK_TODAY", date.today().isoformat()))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="desk", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("analyse", help="classify, rank and plan the portfolio in data/portfolio")
    a.add_argument("--today")
    a.add_argument("--use-case", help="print one use case's dossier")

    e = sub.add_parser("eval", help="run an evaluation set (evals/dev or heldout/<set>)")
    e.add_argument("set", help="'dev' or a held-out set name")

    pv = sub.add_parser("ask", help="ask a proof of value through its approval")
    pv.add_argument("use_case", choices=["lws-wohngeld-auskunft", "stmv-kleine-anfragen"])
    pv.add_argument("message")
    pv.add_argument("--today")

    db = sub.add_parser("db", help="migrate, seed and replan the PostgreSQL record (DESK_DATABASE_URL)")
    db.add_argument("what", choices=["migrate", "seed", "replan", "all"])
    db.add_argument("--today")

    tk = sub.add_parser("token", help="mint a development token (DESK_AUTH=dev)")
    tk.add_argument("--sub", default="architect@example.org")
    tk.add_argument("--role", default="architect", choices=["architect", "specialist", "customer"])
    tk.add_argument("--customers", default="lws,stmv,lechfeld,bafm")

    sub.add_parser("sim", help="regenerate the fictional usage exports")
    sv = sub.add_parser("serve", help="the API and the desk MCP server")
    sv.add_argument("--port", type=int, default=8080)

    args = ap.parse_args(argv)

    if args.cmd == "analyse":
        from desk.analysis import analyse
        from desk.model import load_portfolio

        an = analyse(load_portfolio(), _today(args.today))
        if args.use_case:
            cl = an.classifications[args.use_case]
            print(
                json.dumps(
                    {
                        "classification": cl.as_dict(),
                        "path": an.plan.as_dict()["useCases"].get(args.use_case),
                        "architecture": an.architectures[args.use_case].as_dict()
                        if args.use_case in an.architectures
                        else None,
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return 0
        plan = an.plan.as_dict()
        for c in an.customers:
            print(c.name)
            for u in c.use_cases:
                cl = an.classifications[u.id]
                p = plan["useCases"].get(u.id) or {}
                when = p.get("goLive") or (
                    f"ready {p['readyBy']}, waits for {p['waitingFor']}" if p.get("waitingFor") else ""
                )
                stop = ", ".join(k for k, _ in cl.stops)
                print(f"  {u.id:28} {u.stage:20} {cl.ai_act_class:13} {stop or when}")
        print("\nBottlenecks:", json.dumps(plan["bottlenecks"], ensure_ascii=False))
        print("Levers:")
        for lv in an.levers[:6]:
            print(f"  {lv['weeksSaved']:3} weeks  {lv['lever']}")
        return 0

    if args.cmd == "eval":
        from desk.evals import evaluate, run_heldout

        r = evaluate(Path("evals/dev")) if args.set == "dev" else run_heldout(args.set)
        print(r["headline"])
        return 0

    if args.cmd == "ask":
        from desk.approval import compile_scope, load_all
        from desk.classify import classify
        from desk.model import load_portfolio
        from desk.pov.runtime import run_anfrage, run_enquiry

        by = {u.id: (u, c) for c in load_portfolio() for u in c.use_cases}
        u, c = by[args.use_case]
        scope = compile_scope(load_all()[args.use_case], classify(u, c), _today(args.today))
        if args.use_case == "lws-wohngeld-auskunft":
            result = asyncio.run(run_enquiry(args.message, scope)).as_dict()
        else:
            result = asyncio.run(run_anfrage(args.message, scope)).as_dict()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if args.cmd == "db":
        from desk.store import Store

        st = Store(os.environ["DESK_DATABASE_URL"])
        if args.what in ("migrate", "all"):
            print("migrated:", st.migrate())
        if args.what in ("seed", "all"):
            print("seeded:", st.seed())
        if args.what in ("replan", "all"):
            print("planned:", st.replan(_today(args.today)))
        return 0

    if args.cmd == "token":
        from desk.auth import mint_dev

        print(mint_dev(args.sub, args.role, [c for c in args.customers.split(",") if c]))
        return 0

    if args.cmd == "sim":
        from desk.sim import generate

        for p in generate():
            print(p)
        return 0

    if args.cmd == "serve":
        import uvicorn

        uvicorn.run("desk.api:create_app", factory=True, host="0.0.0.0", port=args.port)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
