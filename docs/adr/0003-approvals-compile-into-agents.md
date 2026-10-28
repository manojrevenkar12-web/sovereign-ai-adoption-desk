# 3. Approvals compile into the agent, and the server enforces them too

**Context.** Public bodies approve a scope on paper (target, data, tools, oversight); the software
then drifts. A policy document next to an unrestricted agent does not hold.

**Decision.** The agent (OpenAI Agents SDK) is built from the approval record: approved MCP tools only
(client-side filter), pseudonymisation when personal data are accepted, forbidden intents handed over
by rules before any model call, an output guardrail on every statement. The desk signs a short-lived
token carrying the approval; each MCP server (MCP v2, streamable HTTP) checks it and enforces tools and
the data ceiling itself. Approvals expire and are invalidated when the discovery answers or the AI Act
class change.

**Consequences.** A misconfigured client cannot widen the scope. Classified records are withheld and
counted, never sent; the draft says one was withheld so a person handles it.
