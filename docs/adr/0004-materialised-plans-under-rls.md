# 4. Compute the portfolio once, read it under row-level security

**Context.** Planning needs the whole portfolio (capacity is shared); readers must see only their
customers, including the customer's own staff.

**Decision.** The planner runs as `desk_planner`, recomputes after every change and writes one plan row
per use case and one view per customer. Requests run as `desk_app` with `desk.customers` from the
OpenID Connect token; PostgreSQL policies filter every table. The desk's MCP server for ChatGPT and
Codex uses the same tokens and the same policies.

**Consequences.** Reads are cheap and isolated by the database, not by convention. A write is followed
by a full replan (fast at portfolio sizes an architect owns).
