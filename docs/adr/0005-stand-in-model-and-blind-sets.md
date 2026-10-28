# 5. A deterministic stand-in model in CI; blind sets for every claim

**Context.** CI must be reproducible and free; claims about the proofs of value must not be tuned on
the cases that measure them.

**Decision.** The agents run on a stand-in implementing the Agents SDK `Model` interface: it calls the
same MCP tools and returns the same structured output, extractively. With `OPENAI_API_KEY` and
`DESK_LIVE=1` the same agents run on the approved model. Blind sets are written from guides by someone
who has not seen the code, run once, and pinned; studying a set's failures retires it to regression.

**Consequences.** CI measures retrieval, routing, scope enforcement and verification, not model
quality. pov-1's failures were studied, so pov-2 was written blind to measure the fixes.
