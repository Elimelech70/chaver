# Code Review — Web Search Sensory Module (`57b6009..be0b80c`)

**Date:** 2026-08-10
**Reviewer:** Claude Code
**Scope:** 7 commits pulled from `origin/main` — `chaver/sensory/web_search.py` and its wiring into `chaver/heartbeat.py`, plus supporting doc/config changes.

---

## What landed

- New `chaver/sensory/web_search.py` — Tavily-backed web search, wired into `heartbeat.py`.
- `chaver/state.py` — new optional `web_search` field on `ChaverState`.
- `deploy/laptop/chaver.service` — laptop systemd unit.
- `pyproject.toml` — new `search` extra (`tavily-python`).
- `.env.example` — `TAVILY_API_KEY`, `CHAVER_SEARCH_RESULTS`.
- Doc updates: `docs/Chaver Conceptual Architecture.md`, `docs/AI Architecture research.md`, `docs/Implementation/LAPTOP_IMPLEMENTATION_REPORT.md`.

## Findings

### 1. Likely violates CLAUDE.md principle 8 and is an unapproved roadmap item

CLAUDE.md principle 8: *"No cognitive call crosses the network except the language faculty. Embedding, binding, recall, and storage are always local regardless of which language backend is active."*

`web_search.py` (lines 1–19) explicitly addresses principle 2 ("no language faculty calls here") but does not address principle 8 — Tavily is a second network dependency invoked mid-conversation-turn, not from the language faculty. CLAUDE.md's roadmap section lists "sensor ingest (market data, news) driving attention automatically" as **v0.5, deferred, requiring design discussion first**, and states plainly: *"Do not silently add these."* The search-on-recall-gap mechanism added here is functionally that feature, added without the flagged discussion.

**Recommendation:** confirm with Craig this was intentional before building further on top of it.

### 2. Blocking network call held under the shared turn lock, no timeout

`heartbeat.py:199–219` — `handle_turn` acquires `lock` at the top of the function, and when hippocampal recall similarity is low, `await web_search_enrich(...)` runs *inside* that lock. This lock is shared across stdin, telnet, and Telegram transports (`heartbeat.py:395–396`). The underlying Tavily call (`web_search.py:96`, `client.search(...)`) has no timeout set. If Tavily hangs, every transport stalls — no exception is raised for the `try/except` to catch, since a hang never returns.

This cuts against the project's stated convention that "Chaver's heartbeat should keep beating even if one subsystem hiccups."

**Recommendation:** add an explicit timeout to the Tavily call, and/or move the search out from under the shared turn lock.

### 3. Gap threshold defaults to searching very often early in a session

`heartbeat.py:217` — `top_similarity = max((r.similarity for r in recalled), default=0.0)`. An empty or thin hippocampus (early in a session, or before much has consolidated) means nearly every turn falls below `SEARCH_GAP_THRESHOLD` and triggers a Tavily call. Not a bug, but worth flagging for API cost/rate-limit awareness once `TAVILY_API_KEY` is set in production.

### 4. Doc quality — `docs/Chaver Conceptual Architecture.md`

The new "Introduction" section has a sentence that trails off mid-thought ("...has a prefrontal cortex that has attention, strategy,") and several typos ("reeplicated", "memeory", "matrix"). Cosmetic, but this is one of the two "read first" architecture docs referenced at the top of CLAUDE.md, so worth a cleanup pass.

## What looks fine

- Lazy Tavily import, `available` property gated on env var, errors caught and logged rather than propagated — consistent with existing conventions.
- `state.py` field addition is properly optional/typed, matches the dataclass convention.
- `pyproject.toml` / `.env.example` wiring for the new `search` extra is consistent and correctly cross-referenced.
- No language-faculty bypass — search results enter via working memory excitation and hippocampal storage, not a direct LLM call.

## Bottom line

Mechanically sound and consistent with most coding conventions, but introduces a second network-crossing subsystem that reads as a pre-emptive implementation of a roadmap item (v0.5 sensor ingest) CLAUDE.md explicitly gates behind design discussion. Recommend confirming intent with Craig, and independently fixing the lock/timeout issue (#2) regardless of the architectural question, since it's a real hang risk today.
