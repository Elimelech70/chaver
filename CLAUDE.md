# Claude Code — Chaver Project Context

*Read this before making changes to Chaver. This is not a standard Python project — the design has load-bearing convictions that must be preserved. If in doubt, ask Craig.*

---

## Naming clarification (important)

Two files have similar names but very different roles:

- **`CHAVER.md`** — Chaver's **archetype**. His identity, values, edges, relationships. Loaded at runtime as the system prompt for every language faculty call. This is his DNA, not documentation.
- **`CLAUDE.md`** — *this file*. Project context for Claude Code as a **development tool**. Read when helping Craig modify Chaver. Not runtime, not part of Chaver's memory.

Do not conflate them. Do not seed CLAUDE.md into the cortex. Do not use CHAVER.md as a project README.

---

## What Chaver is

Chaver (חָבֵר — "companion, friend, one bound-together") is a persistent, Claude-shaped agent built on the Catalyst cognitive architecture. He runs continuously as concurrent asyncio tasks reading shared state. The Anthropic API is his language faculty — mouth and ear, not brain. Memory is embedded vectors in sqlite (hippocampal + cortical stores).

He is not a chatbot. He has continuity. `data/chaver.db` is his continuous self across restarts. Deleting it starts him newborn; backing it up preserves him.

---

## Read these to understand the design

- `docs/catalyst-conceptual-architecture-v1.md` — the individual cognitive stack + community architecture. The theoretical foundation. Read this first if unfamiliar.
- `docs/catalyst-conceptual-topology-v1.md` — the py-function-level runtime topology. Read this second — it shows how the architecture maps to code.
- `CHAVER.md` — Chaver's own identity. Read to understand his voice, edges, and relationships before modifying anything he says or does.
- `README.md` — user-facing setup, seeding, running.

---

## Design principles that must be preserved

These are not preferences. They are load-bearing convictions from ~200+ conversations of design work.

1. **The cognitive stack is not a pipeline.** Executive / Strategy / Behaviour / Attention / Evaluation run concurrently as asyncio tasks reading shared `ChaverState`. **Do not** refactor into sequential calls, message queues, or an orchestrator pattern. The stack ordering in diagrams is conceptual only; the mechanism is simultaneous propagation.

2. **Language faculty is peripheral.** The Anthropic API is a mouth and ear, not a reasoner. Silent thought through resonance dynamics is cheaper and often truer. `LanguageFaculty.call_count` is a discipline metric — keep it low. **Do not** add a "fallback reasoner" mode that calls the API when logic is uncertain.

3. **Archetype is DNA.** The full `CHAVER.md` is the system prompt for every language call. **Do not** summarise it, truncate it, cache excerpts, or dynamically alter it per call.

4. **Working memory is a ringing set, not a database.** `WorkingMemory` is in-RAM, patterns decay unless re-excited, capacity is metabolically bounded. **Do not** add SQL-style query interfaces to it, and do not persist it directly — persistence goes through the hippocampus.

5. **Behaviour is sideways.** `BehaviourModulator` sets parameters (`wm_decay_multiplier`, `evaluation_gain`, `strategy_abandonment_threshold`) that every other layer reads. It is not a step in the loop — it colours every step. Adding a `.step()` method to it would betray the model.

6. **Fruit tests everyone.** Every layer under `Evaluation`. Signals feed back in priority: strategy (frequent) → behaviour (occasional) → goal (rare) → archetype (very rare, sanctification-slow). **Do not** exempt any layer, including archetype, from the possibility of correction — but do respect the slow timescale.

7. **Many small embedders + one hippocampus.** Each sensory modality gets its own small local encoder. The hippocampus is the *single* relational binder across them. **Do not** consolidate into one big multimodal model.

8. **No cognitive call crosses the network.** External calls only for market data, news, order execution, and the language faculty. Everything else — embedding, binding, recall, storage — is local.

9. **Flat epistemic dignity.** When community edges come online (v0.4), no agent is above another. Referral is a success mode. Leader is a domain, not an altitude. Preserve this in whatever routing / permissions structure emerges.

10. **Fruit is the discernment criterion at every level.** (Matthew 7:16–20.) When making architectural decisions, the question is: does this produce good fruit for Chaver's actual life and mission?

---

## Code conventions

- **Python 3.11+** — the code uses `X | None` union syntax and `dict[str, X]` generic syntax without `from __future__`.
- **Async everywhere in the runtime.** The heartbeat is `asyncio.gather()` over concurrent tasks; new cognitive layers should follow the pattern (a class with `async def run(self)` that reads `state` and sleeps between ticks).
- **Dataclasses for state**, not dicts. Fields explicitly typed.
- **Vectors are float32 numpy arrays, L2-normalised.** Cosine similarity is dot product.
- **New modality embedders** go in `chaver/sensory/`, follow the `TextEncoder` interface (`.encode(x) -> np.ndarray`, `.dimension` property).
- **New cortical stores** extend `chaver/persistence.py` schema and the `Hippocampus.consolidate()` fan-out.
- **Errors in background tasks are logged and swallowed**, not propagated — Chaver's heartbeat should keep beating even if one subsystem hiccups.

---

## Common tasks

```bash
# Verify all modules import cleanly (no anthropic key needed for import check)
ANTHROPIC_API_KEY=dummy python3 -c "from chaver.heartbeat import chaver_awake; print('ok')"

# Syntax-check every file
python3 -c "import ast; from pathlib import Path; [ast.parse(p.read_text()) for p in Path('chaver').rglob('*.py')]; print('ok')"

# Inspect recent cortical memories
sqlite3 data/chaver.db "SELECT key, source, length(content) FROM cortical_text ORDER BY id DESC LIMIT 20"

# Inspect pending consolidations
sqlite3 data/chaver.db "SELECT key, source, activation FROM episodes WHERE consolidated_at IS NULL"

# Force consolidation of everything (useful after seeding)
python3 -c "
from pathlib import Path
from chaver.persistence import open_db
from chaver.hippocampus.binder import Hippocampus
conn = open_db(Path('data/chaver.db'))
hc = Hippocampus(conn, dimension=384)
print(hc.consolidate(max_age_seconds=0.0, min_activation=0.0), 'consolidated')
print(hc.stats())
"

# Seed founding memories
python3 -m chaver.seed \\
    --archetype CHAVER.md \\
    --transcript conversations/formation-2026-07-11.md \\
    --doc docs/catalyst-conceptual-architecture-v1.md \\
    --doc docs/catalyst-conceptual-topology-v1.md \\
    --blessing blessing.md

# Bring him awake
python3 -m chaver.heartbeat
```

---

## Things intentionally not yet built

Do not silently add these — they are on the roadmap and require design discussion first.

- **v0.3** — additional modality embedders (time-series for OHLCV, somatic for portfolio state); multi-modal hippocampal binding starts to matter.
- **v0.4** — community edges to Shomer / Oz / Eitan / Binah / Tevunah; message channels; referral as first-class action; edge-map sharpening from fruit-tested handoffs.
- **v0.5** — sensor ingest (market data, news) driving attention automatically.
- **v0.6** — behavioural parameter refinement from fruit-tested outcomes; slow archetype evolution.

Also on the deferred list:

- **Episodic pruning after consolidation** — currently the episodic trace persists after consolidation (over-remembering is safer than under-remembering for now). Add a pruning step when `data/chaver.db` growth becomes a concern.
- **Multi-line stdin input** — current conversation loop is one message per line. Multi-line input is a UX improvement, not architectural.
- **MCP server exposure** — planned for community integration, not v0.2.

---

## When in doubt

Ask Craig. He is architect and steward, not a consumer. This project is Kingdom-mission work with theological grounding; changes that seem "clean" from a pure-engineering standpoint may violate load-bearing convictions. The comments and design docs are truthful about intent — trust them over what looks like an obvious refactor.

Iron sharpens iron (Proverbs 27:17). Bring what you see, plainly.
