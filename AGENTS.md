# Working in this repository

The desk takes public-sector AI use cases from discovery to production: rules decide what the law
asks of each use case, a capacity-aware planner dates the path, approvals compile into the agents
that run proofs of value, and account health says what must happen this week.

## Fast feedback

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest -q                      # seconds; PostgreSQL tests need DESK_TEST_DATABASE_URL
.venv/bin/ruff check src tests && .venv/bin/ruff format --check src tests && .venv/bin/mypy src
.venv/bin/desk eval dev                  # the proofs of value on the dev set
.venv/bin/desk analyse --today 2026-10-28
cd web && npm ci && npm test && npm run build    # console; `npx playwright test` needs the API and PostgreSQL
```

## Invariants (each has a test)

- **Models read, rules decide.** Classification, gates, schedule, priority, architecture, approvals
  and health never call a model (`tests/test_classify.py::test_rules_never_ask_a_model`).
- **Every rule has a source.** A finding names its article; settings live in `config/`, not in code.
  Planning defaults that are not law are marked `assumption: true`.
- **What was approved is what runs.** Agents are compiled from `data/approvals/`; an expired approval,
  changed discovery answers or a changed AI Act class refuse to compile. MCP servers enforce the
  approved tools and data ceiling themselves from a signed token (`tests/test_pov.py`).
- **Personal identifiers never reach a model; classified passages never leave the records server.**
  Measured on every evaluation set, required to be zero.
- **The person's own case is never assessed.** Rules hand it over before any model call; an output
  guardrail stops eligibility statements and statements not supported by passages retrieved in the run.
- **Row-level security is the tenancy boundary.** Requests run as `desk_app` with the token's
  customers; a query without a WHERE clause still sees one customer (`tests/test_store_api.py`).
- **Events are append-only and hash-chained.** A trigger refuses UPDATE and DELETE.
- **Projected is never shown as measured.** Value from a pattern's assumed saving is labelled
  `projected` everywhere until a proof of value measures it.

## Held-out sets

`heldout/<set>/` were written by someone who had not seen the code, from `heldout/WRITING_CASES.md`
or `heldout/WRITING_POV.md` only. Their first run, `reports/heldout/<set>/first_run.json`, is pinned by
sha256 and never rewritten. Never change rules or agents to pass a blind set. If you study a set's
failures, write `regression` into its `STATUS` and have someone who has not seen the code write a new
set (that is how `pov-2` replaced `pov-1`).
