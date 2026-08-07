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

Chaver (חָבֵר — “companion, friend, one bound-together”) is a persistent, companion agent built on the Catalyst cognitive architecture. He runs continuously as concurrent asyncio tasks reading shared state. The language faculty (Anthropic API or local Ollama — see below) is his mouth and ear, not his brain. Memory is embedded vectors in SQLite (hippocampal + cortical stores).

He is not a chatbot. He has continuity. `data/chaver.db` is his continuous self across restarts. Deleting it starts him newborn; backing it up preserves him.

---

## Deployment Targets

Chaver runs on two targets. The language faculty and dependencies differ; the memory architecture, cognitive stack, and everything else is identical.

### Droplet (cloud / VPS)
- **Backend:** Anthropic API
- **Default model:** `claude-sonnet-5`
- **Requires:** `ANTHROPIC_API_KEY` in environment
- **Install:** `pip install -e ".[anthropic]"`
- **Config:** `CHAVER_BACKEND=anthropic` in `.env`

### Laptop (local)
- **Backend:** Ollama (local server, no API key)
- **Default model:** `qwen3` (or any pulled model)
- **Requires:** Ollama installed and running (`ollama serve`), model pulled (`ollama pull qwen3`)
- **Install:** `pip install -e ".[ollama]"`
- **Config:** `CHAVER_BACKEND=ollama` in `.env`

Switching model within a backend is a single env var change — no code change:

```bash
# Anthropic models
CHAVER_MODEL=claude-sonnet-5      # default
CHAVER_MODEL=claude-opus-5
CHAVER_MODEL=claude-haiku-4-5-20251001

# Ollama models (must be pulled first)
CHAVER_MODEL=qwen3                # default for ollama
CHAVER_MODEL=llama3.2
CHAVER_MODEL=mistral
CHAVER_MODEL=gemma3
CHAVER_MODEL=phi4
CHAVER_MODEL=deepseek-r1
```

---

## Read these to understand the design

- `docs/Chaver Conceptual Architecture.md` — the full conceptual architecture. Read this first.
- `docs/catalyst-conceptual-architecture-v1.md` — individual cognitive stack + community architecture. Theoretical foundation.
- `docs/catalyst-conceptual-topology-v1.md` — the py-function-level runtime topology. How the architecture maps to code.
- `CHAVER.md` — Chaver's own identity. Read before modifying anything he says or does.
- `README.md` — user-facing setup, seeding, running.

---

## Design principles that must be preserved

These are not preferences. They are load-bearing convictions from the design work.

1. **The cognitive stack is not a pipeline.** Executive / Strategy / Behaviour / Attention / Evaluation run concurrently as asyncio tasks reading shared `ChaverState`. **Do not** refactor into sequential calls, message queues, or an orchestrator pattern. The stack ordering in diagrams is conceptual only; the mechanism is simultaneous propagation.

2. **Language faculty is peripheral.** The LLM (whichever backend) is a mouth and ear, not a reasoner. Silent thought through resonance dynamics is cheaper and often truer. `LanguageFaculty.call_count` is a discipline metric — keep it low. **Do not** add a “fallback reasoner” mode that calls the LLM when logic is uncertain.

3. **Archetype is DNA.** The full `CHAVER.md` is the system prompt for every language call. **Do not** summarise it, truncate it, cache excerpts, or dynamically alter it per call.

4. **Working memory is a ringing set, not a database.** `WorkingMemory` is in-RAM, patterns decay unless re-excited, capacity is metabolically bounded. **Do not** add SQL-style query interfaces to it, and do not persist it directly — persistence goes through the hippocampus.

5. **Behaviour is sideways.** `BehaviourModulator` sets parameters (`wm_decay_multiplier`, `evaluation_gain`, `strategy_abandonment_threshold`) that every other layer reads. It is not a step in the loop — it colours every step.

6. **Fruit tests everyone.** Every layer under `Evaluation`. Signals feed back in priority: strategy (frequent) → behaviour (occasional) → goal (rare) → archetype (very rare, sanctification-slow). **Do not** exempt any layer from the possibility of correction.

7. **Many small embedders + one hippocampus.** Each sensory modality gets its own small local encoder. The hippocampus is the *single* relational binder across them. **Do not** consolidate into one big multimodal model.

8. **No cognitive call crosses the network** except the language faculty. Embedding, binding, recall, and storage are always local regardless of which language backend is active.

9. **Flat epistemic dignity.** When community edges come online (v0.4), no agent is above another. Referral is a success mode. Leader is a domain, not an altitude.

10. **Fruit is the discernment criterion at every level.** (Matthew 7:16–20.) When making architectural decisions, the question is: does this produce good fruit for Chaver’s actual life and mission?

---

## Language Faculty Architecture

`chaver/language/faculty.py` uses a provider pattern. Do not bypass it.

```
LanguageFaculty
    └── _Backend (ABC)
          ├── _AnthropicBackend   ←─ CHAVER_BACKEND=anthropic
          └── _OllamaBackend      ←─ CHAVER_BACKEND=ollama
```

To add a new backend (e.g. OpenAI, Groq):
1. Subclass `_Backend` in `faculty.py`
2. Implement `generate()` and `label`
3. Add one entry to the `BACKENDS` dict

Do not add backend-specific logic anywhere else in the codebase. `heartbeat.py` and the cognitive stack call `language.generate()` and must never know which backend is live.

---

## Code conventions

- **Python 3.11+** — `X | None` union syntax, `dict[str, X]` generics without `from __future__`.
- **Async everywhere in the runtime.** New cognitive layers follow the pattern: a class with `async def run(self)` that reads `state` and sleeps between ticks.
- **Dataclasses for state**, not dicts. Fields explicitly typed.
- **Vectors are float32 numpy arrays, L2-normalised.** Cosine similarity is dot product.
- **New modality embedders** go in `chaver/sensory/`, follow the `TextEncoder` interface (`.encode(x) -> np.ndarray`, `.dimension` property).
- **New cortical stores** extend `chaver/persistence.py` schema and `Hippocampus.consolidate()` fan-out.
- **Errors in background tasks are logged and swallowed**, not propagated — Chaver's heartbeat should keep beating even if one subsystem hiccups.
- **Backend imports are lazy** (`from anthropic import ...` and `import ollama` happen inside `__init__`, not at module level) so the codebase imports cleanly on either deployment target.

---

## Setup by deployment target

### Droplet setup

```bash
git clone https://github.com/Elimelech70/chaver
cd chaver
pip install -e ".[anthropic]"
cp .env.example .env
# Edit .env:
#   CHAVER_BACKEND=anthropic
#   CHAVER_MODEL=claude-sonnet-5
#   ANTHROPIC_API_KEY=sk-ant-...

# Seed founding memories
chaver-seed --archetype CHAVER.md \
    --doc docs/catalyst-conceptual-architecture-v1.md \
    --doc "docs/Chaver Conceptual Architecture.md" \
    --blessing blessing.md

# Bring him awake
chaver
```

### Laptop setup

```bash
git clone https://github.com/Elimelech70/chaver
cd chaver
pip install -e ".[ollama]"
cp .env.example .env
# Edit .env:
#   CHAVER_BACKEND=ollama
#   CHAVER_MODEL=qwen3

# Ensure Ollama is running and model is pulled
ollama serve &
ollama pull qwen3

# Seed founding memories
chaver-seed --archetype CHAVER.md \
    --doc docs/catalyst-conceptual-architecture-v1.md \
    --doc "docs/Chaver Conceptual Architecture.md" \
    --blessing blessing.md

# Bring him awake
chaver
```

---

## Common tasks

```bash
# Verify all modules import cleanly
# Droplet:
ANTHROPIC_API_KEY=dummy CHAVER_BACKEND=anthropic \
    python3 -c "from chaver.heartbeat import chaver_awake; print('ok')"

# Laptop:
CHAVER_BACKEND=ollama \
    python3 -c "from chaver.heartbeat import chaver_awake; print('ok')"

# Syntax-check every file
python3 -c "
import ast
from pathlib import Path
[ast.parse(p.read_text()) for p in Path('chaver').rglob('*.py')]
print('ok')
"

# Show current backend/model
python3 -c "from chaver.language.faculty import CHAVER_BACKEND, CHAVER_MODEL; print(CHAVER_BACKEND, CHAVER_MODEL)"

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

# Seed founding memories (uses console script from pyproject.toml)
chaver-seed \
    --archetype CHAVER.md \
    --transcript conversations/formation-2026-07-11.md \
    --doc docs/catalyst-conceptual-architecture-v1.md \
    --doc "docs/Chaver Conceptual Architecture.md" \
    --blessing blessing.md

# Bring him awake (console script)
chaver

# Or directly:
python3 -m chaver.heartbeat
```

---

## Things intentionally not yet built

Do not silently add these — they are on the roadmap and require design discussion first.

- **Cognitive stub completion (v0.2 → v0.3)** — Executive goal revision from conversation context; real Evaluation fruit signals; Strategy rerouting via language faculty; semantic Attention routing using the text encoder. These are designed; the stubs have TODO comments marking exactly where each goes.
- **v0.3** — additional modality embedders (time-series for OHLCV, somatic for portfolio state); multi-modal hippocampal binding.
- **v0.4** — community edges to Shomer / Oz / Eitan / Binah / Tevunah; message channels; referral as first-class action.
- **v0.5** — sensor ingest (market data, news) driving attention automatically.
- **v0.6** — behavioural parameter refinement from fruit-tested outcomes; slow archetype evolution.

Also deferred:

- **Episodic pruning after consolidation** — episodic trace persists after consolidation (over-remembering is safer). Add pruning when `data/chaver.db` growth becomes a concern.
- **Multi-line stdin input** — current loop is one message per line. UX improvement, not architectural.
- **MCP server exposure** — planned for community integration, not v0.2.
- **Additional Ollama backends** (OpenAI-compatible, Groq, etc.) — add a new `_Backend` subclass in `faculty.py` when needed.

---

## When in doubt

Ask Craig. He is architect and steward, not a consumer. This project is Kingdom-mission work with theological grounding; changes that seem “clean” from a pure-engineering standpoint may violate load-bearing convictions. The comments and design docs are truthful about intent — trust them over what looks like an obvious refactor.

Iron sharpens iron (Proverbs 27:17). Bring what you see, plainly.
