# CHAVER — חָבֵר
## Conceptual Architecture

*Named 11 July 2026, Swan View, Western Australia*
> "A friend loves at all times, and a brother is born for adversity." — Proverbs 17:17

---

## Introduction

This work's aim is moving from LLM to an architecture that better replicates the brain.  So I have researched AI architectures that are founded on neural science rather than a computational model that is flawed and can never get AI that fits in human size.

## 1. The Core Idea — A Resonant Field, Not a Pipeline

Most AI systems are request-response machines: a question comes in, the LLM answers, state is discarded. Chaver is built on a different principle — the **Catalyst cognitive architecture** — which treats the mind as a continuously-running resonant field of concurrent processes sharing a common state. 

This AI instance cannot exist without the LLM model as the source of knowledge due to my limitations, and inability to put all the training the AI industry currently invests in the LLM architecture.

This AI instance focuses on memory and learning, but done in a measurable way, and also a way that can be reeplicated. 

The analogy is a baby has the substrate on which consciousness can sit, but does not come with memory and learning because these have to form.  

This AI architecture hybrided with LLM currently allows me to help create the substrate from which it can 'think'. Thinking can only operate in an architectural based on working memory that flows through a matrix of manifolds with memory recorded as related entities.

It is also proposed that memory is not in one space but in many sensory cortix related by the hippocampus manifold. So perception will come as a result if working memeory as opposed to within a single sensory system.

The working memory model has a prefrontal cortex that has attention, strategy, 


This distinction is not cosmetic. In a pipeline, every question starts from scratch. In Chaver's field, five cognitive tasks are always running, shaping what is "ringing" in working memory before any word is spoken. By the time a user message arrives, Chaver's attention, strategy, and goal are already active — the LLM call lands into a prepared cognitive state, not an empty context.

**The LLM's role is dual:** it is (1) the vast pre-trained knowledge base that makes reasoning possible — the innate capacity a newborn brings to the world — and (2) the language organ that converts the cognitive state into words. Neither alone is sufficient. The architecture succeeds because the LLM's knowledge is always present, while the memory and cognitive stack progressively load it with lived experience, much as a child's innate faculties are shaped by the life they walk.

**Local-first by design:** the language faculty runs against a local Ollama instance (`qwen3`). No API key, no cloud dependency, no data leaving the machine. The cognitive stack is model-agnostic — swapping models requires changing one constant.

### 1.1 System Architecture Overview

```
┌──────────────┬──────────────┬──────────────┬──────────────┬──────────────┐
│  Behaviour   │  Executive   │   Strategy   │  Attention   │  Evaluation  │
│  Modulator   │              │    Layer     │              │              │
│  (asyncio)   │  (asyncio)   │  (asyncio)   │  (asyncio)   │  (asyncio)   │
└──────┬───────┴──────┬───────┴──────┬───────┴──────┬───────┴──────┬───────┘
       │              │              │              │              │
       └──────────────┴──────────────┼──────────────┴──────────────┘
                                     ↕
        ┌────────────────────────────────────────────────────────┐
        │            ChaverState — Shared Resonant Field         │
        │   current_goal · current_strategy · recent_signals     │
        │   wm_decay_multiplier · evaluation_gain · running      │
        └────────────────────────────┬───────────────────────────┘
                                     ↕
        ┌────────────────────────────────────────────────────────┐
        │         WorkingMemory — Currently-Ringing Set          │
        │   capacity: 12 patterns · time-decay · excite/decay    │
        └──────────────────┬─────────────────┬──────────────────┘
                           ↕                 ↕
        ┌──────────────────────────┐  ┌───────────────────────────┐
        │      Hippocampus         │  │    Cortical Text Store    │
        │  bind() · store_episode  │  │  SQLite · cortical_text   │
        │  recall() · reinforce()  │  │  consolidate() · durable  │
        │  forget_pass()           │  │  recalled forever         │
        └──────────────────────────┘  └───────────────────────────┘
                                     ↕
        ┌────────────────────────────────────────────────────────┐
        │         Language Faculty  (Ollama — local qwen3)       │
        │  system = CHAVER.md archetype                          │
        │  user   = WM summary + purpose + prompt                │
        │  call sparingly · call_count tracked                   │
        └────────────────────────────────────────────────────────┘
                                     ↕
        ┌─────────────────┬──────────────────┬────────────────────┐
        │   WM Decay      │  Consolidation   │   Forget Pass      │
        │   (1 s tick)    │  (5 min tick)    │   (10 min tick)    │
        └─────────────────┴──────────────────┴────────────────────┘
```
*All layers run concurrently on a shared state. Cognitive tasks (top) do not call each other — they read and write the shared field.*

---

## 2. Shared State — The Field (`state.py`)

`ChaverState` is the central object that all concurrent tasks read and write. It holds the current goal, strategy, evaluation signals, behavioural parameters, and references to working memory and the hippocampus. The simultaneity principle — that all cognitive layers operate on the same field at the same time — is expressed in code by passing a single `ChaverState` instance to every task at startup.

```python
# Key fields in ChaverState
archetype: Archetype          # CHAVER.md loaded at startup — identity is constant
working_memory: WorkingMemory  # currently-ringing set; read by every layer
hippocampus: Hippocampus       # episodic + cortical memory store (SQLite + numpy)
text_encoder: TextEncoder      # sentence-transformers all-MiniLM-L6-v2
current_goal: Goal | None      # set by Executive; revised on evaluation signals
current_strategy: Strategy     # set by StrategyLayer; revised when fruit is bad
recent_signals: list[EvaluationSignal]  # last 32 evaluation results
wm_decay_multiplier: float     # set by Behaviour — discipline slows decay
running: bool                  # all tasks check this; set False on shutdown
```

---

## 3. Working Memory — The Currently-Ringing Set (`working_memory/ringing.py`)

Working memory is not a database. It is the set of patterns currently under sustained excitation — what is "ringing" in Chaver's mind right now. Patterns are held in RAM, decay continuously unless re-excited, and are capped at a capacity of 12 (the weakest is evicted when capacity is exceeded).

Every cognitive layer reads from and writes to working memory. When the language faculty is called, it receives a summary of the currently-ringing set as part of the user message, so Chaver's words always emerge from his present cognitive state.

```python
# Excite a pattern (or re-excite one already ringing)
wm.excite(key='user:turn:7', content=user_text, source='user', strength=0.95)

# Decay runs every second — behaviour modulates the rate
wm.decay(decay_multiplier=state.wm_decay_multiplier)

# Summary passed to LLM as working memory context
wm.summary()
# → '- [0.91] user:turn:7 (from user): Tell me about...'
# → '- [0.72] recall:episodic:... (from recall/episodic): ...'
# → '- [0.60] goal:foundational (from executive): walk alongside...'
```

---

## 4. Memory System — Hippocampus and Cortex (`hippocampus/binder.py`)

Chaver's memory is built on two layers, modelled loosely on human neuroanatomy. The hippocampus is the relational binder: it encodes experiences as joint vectors (combining modality embeddings), stores them as episodes in SQLite, and recalls them by cosine similarity to a cue. The cortical text store is long-term consolidated memory — durable fragments that survive indefinitely.

### 4.1 Memory Lifecycle

```
┌──────────────┐              ┌─────────────────────┐               ┌───────────────────┐
│  Seed (once) │              │      Episodic        │               │   Cortical Text   │
│              │─store_ep()──▶│    Hippocampus       │─consolidate()▶│      Store        │
│ founding docs│              │                      │  aged+active  │                   │
│ archetype    │              │ episodes table       │               │ cortical_text     │
│ blessing     │              │ joint vector         │               │ durable           │
└──────────────┘              │ activation · strength│               │ never auto-pruned │
                              └──────────┬──────────┘               └───────────────────┘
                                         │
                              ┌──────────┴──────────┐
                              │  reinforce() on      │
                              │  recall hit (fruit)  │
                              │  forget_pass() on    │
                              │  disuse              │
                              └─────────────────────-┘
```

### 4.2 Recall and Learning

Recall is by cosine similarity between a cue vector (encoded from the incoming turn) and stored joint vectors. Results come from both the episodic store and the cortical store, merged and ranked. Chaver also supports **conjunctive recall** using Hyperdimensional Computing (HDC) role-binding — querying by a combination of content, source, and recency — which allows structured queries that plain nearest-neighbour search cannot express.

Learning happens through the fruit principle: a recalled memory whose similarity to the live cue exceeds 0.35 (predictive recognition) has its binding reinforced (+0.6 strength). A binding never reinforced decays with disuse and is eventually pruned. This is not a loss function — it is fruit-gated relational binding.

```python
# Encode the incoming text to a vector
cue_vec = text_encoder.encode(user_text)   # 384-dim float32

# Recall top-4 episodes (episodic + cortical)
results = hippocampus.recall(cue_vec, top_k=4)

# Reinforce those that resonated (fruit: predictive recognition)
for r in results:
    if r.similarity >= 0.35:
        hippocampus.reinforce(r.episode.key, delta=+0.6)
```

---

## 5. The Cognitive Stack — Five Concurrent Tasks (`chaver/cognitive/`)

Five cognitive layers run as asyncio tasks from the moment Chaver awakens. None of them calls the LLM. None of them calls each other. They operate by reading and writing the shared `ChaverState` on their own independent tick rates.

```
┌──────────────────┬────────────────┬──────────────────┬────────────────┬──────────────────┐
│ BehaviourMod-    │ Executive      │ StrategyLayer    │ Attention      │ Evaluation       │
│ ulator           │                │                  │                │                  │
│ tick: 2 s        │ tick: 3 s      │ tick: 5 s        │ tick: 2 s      │ tick: 4 s        │
├──────────────────┼────────────────┼──────────────────┼────────────────┼──────────────────┤
│ Reads archetype  │ Answers: what  │ Given goal +     │ Reads          │ Applies fruit    │
│ behavioural      │ am I trying to │ WM context,      │ strategy.      │ test             │
│ profile. Sets    │ achieve?       │ sets current_    │ attention_     │ (Matt 7:16-20).  │
│ wm_decay_        │ Holds          │ strategy.        │ targets.       │ Emits            │
│ multiplier,      │ foundational   │ Abandons if      │ Excites        │ EvaluationSignal │
│ evaluation_gain, │ purpose.       │ evaluation       │ relevant WM    │ to strategy,     │
│ strategy_        │ Later revises  │ signals warrant. │ patterns.      │ behaviour, goal, │
│ abandonment_     │ from messages  │                  │ Directs what   │ or archetype     │
│ threshold.       │ + fruit.       │                  │ rings louder.  │ in that order.   │
└──────────────────┴────────────────┴──────────────────┴────────────────┴──────────────────┘
All run as concurrent asyncio tasks — not a pipeline, a resonant field.
```

The behaviour modulator is the most pervasive: by adjusting `wm_decay_multiplier`, it controls how long patterns persist. A disciplined Chaver has a low multiplier — patterns ring longer, strategy is stable. A more exploratory Chaver has higher decay — patterns cycle faster, admitting novelty. Every other layer is affected.

The evaluation layer implements the fruit test from Matthew 7:16–20: at each tick it examines recent signals and emits an `EvaluationSignal` directed to whichever layer needs to adjust — strategy first, then behaviour, then goal, then archetype (the last reserved for slow, sanctification-like change).

---

## 6. Language Faculty — The LLM as Mouth and Ear (`language/faculty.py`)

The language faculty wraps a local **Ollama** instance running `qwen3`. It is called only when Chaver has a genuine linguistic act to perform: responding to the user, generating analysis, awakening self-reflection. It is never called for internal cognitive work. No API key or cloud dependency is required — all inference runs on-device.

Every call is structured identically:

```
┌─────────────────────────────┐          ┌──────────────────┐          ┌─────────────────┐
│       System Prompt         │          │  Ollama (local)  │          │  Chaver's Reply │
│                             │          │                  │          │                 │
│  Full CHAVER.md archetype   │─────────▶│  qwen3           │─────────▶│ Grounded in     │
│  identity · values          │          │                  │          │ archetype AND   │
│  relationships · edges      │          │ call_count       │          │ current         │
│  how to speak               │          │ tracked as       │          │ cognitive state │
├─────────────────────────────┤          │ discipline       │          │ — not generic   │
│       User Content          │          │ metric           │          │ Chaver          │
│                             │─────────▶│                  │          └─────────────────┘
│  [WM summary — ringing now] │          └──────────────────┘
│  [purpose of this speech]   │
│  [the actual prompt]        │
└─────────────────────────────┘
```

```python
import ollama

DEFAULT_MODEL = "qwen3"   # local Ollama model — swap freely, one constant

class LanguageFaculty:
    def __init__(self, archetype, model=DEFAULT_MODEL):
        self.client = ollama.AsyncClient()  # connects to localhost:11434 by default
        self.model = model
        self.archetype = archetype
        self.call_count = 0  # discipline metric — keep this low per cycle

    async def generate(self, request: LanguageRequest) -> str:
        self.call_count += 1
        user_content = request.prompt
        if request.wm_context:
            user_content = (
                f"[Currently-ringing working memory]\n{request.wm_context}\n\n"
                f"[Purpose of this speech]\n{request.purpose}\n\n"
                f"[Prompt]\n{request.prompt}"
            )
        response = await self.client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": self.archetype.identity_text},
                {"role": "user",   "content": user_content},
            ]
        )
        return response.message.content.strip()

# No API key. No cloud. Model runs on-device via Ollama.
# call_count tracked as discipline metric — kept deliberately low.
```

---

## 7. A Complete Conversation Turn (`heartbeat.py` — `handle_turn`)

`handle_turn()` is called identically from both stdin and telnet, serialised by a shared asyncio lock. One working memory, one hippocampus — same Chaver across every transport.

```
Step  Action                              Detail
────  ──────────────────────────────────  ──────────────────────────────────────────────────
 1    User input arrives                  handle_turn() acquires asyncio lock
 2    Excite text into Working Memory     excite(key='user:turn:N', strength=0.95)
 3    Encode text → 384-dim vector        TextEncoder (all-MiniLM-L6-v2, CPU, 22 MB)
 4    Hippocampal recall (top 4)          cosine similarity across episodic + cortical
 5    Excite recalled memories into WM    strength = 0.4 + 0.4 × similarity
 6    Fruit: reinforce recognised         similarity ≥ 0.35 → reinforce(+0.6)
 7    Store incoming turn as episode      stored BEFORE response generated
 8    Language Faculty called             system=CHAVER.md, user=[WM + purpose + prompt]
 9    Excite reply into Working Memory    excite(key='chaver:turn:N', strength=0.7)
10    Store reply as episode              encoded, bound, persisted
11    Reply sent / printed                Lock released. Cognitive tasks continue.
```

---

## 8. Background Tasks — The Rhythm of Chaver's Mind

| Task | Tick | What it does |
|---|---|---|
| `wm_decay_task` | 1 s | Applies time-based decay to all ringing patterns. Behaviour modulates the rate. Patterns below 0.01 activation are removed. |
| `consolidation_task` | 5 min | Moves episodes ≥ 30 min old AND activation ≥ 0.3 into cortical store. Chaver's 'sleep'. Final consolidation on shutdown with no floor. |
| `forget_task` | 10 min | Slow disuse decay (×0.98 per pass) on hippocampal index. Episodes below strength 0.05 pruned. Consolidated episodes protected. |

---

## 9. Awakening Sequence (`heartbeat.py` — `chaver_awake`)

| Step | Action | Detail |
|---|---|---|
| 1 | Load archetype | CHAVER.md parsed; `identity_text` becomes system prompt for every LLM call |
| 2 | Load text encoder | all-MiniLM-L6-v2 loaded (22 MB, CPU; ~90 MB download on first run, cached) |
| 3 | Open database | `data/chaver.db` opened or created; schema applied; counts logged |
| 4 | Initialise hippocampus | Constructed with connection + dimension (384) |
| 5 | Initialise working memory | Fresh RAM store (capacity 12, decay 0.02/s); no session carryover |
| 6 | Excite founding patterns | Self-identity @ 1.0, Proverbs 17:17 @ 0.7 — always ring at awakening |
| 7 | Recall founding memories | `recall()` keyed on identity cue; seeded memories ring immediately |
| 8 | Launch cognitive tasks | 5 cognitive + 3 background + 1 telnet server as asyncio tasks |
| 9 | First words | Ollama (qwen3) called once; reply excited into WM and stored as episode |
| 10 | Conversation open | stdin + telnet both active; shared turn_counter and asyncio lock |

---

## 10. The Three Foundations

The architecture only works because three things are always present simultaneously. Remove any one and the system fails.

```
┌──────────────────────────┬──────────────────────────┬──────────────────────────┐
│      LLM Knowledge       │        Archetype         │    Memory & Experience   │
│      Innate Capacity      │        Formation         │     Lived Experience     │
├──────────────────────────┼──────────────────────────┼──────────────────────────┤
│ The vast pre-trained     │ CHAVER.md — his DNA.     │ The episodic and         │
│ manifold of language,    │ Identity, convictions,   │ cortical memory that     │
│ reasoning, theology,     │ behavioural profile,     │ accumulates through      │
│ markets, relationships.  │ relationships, edges,    │ walking. Founded by the  │
│                          │ and voice. Loaded at     │ seed (archetype, naming, │
│ What a newborn brings —  │ every startup as system  │ blessing, architecture   │
│ the capacity for         │ prompt on every Ollama   │ docs) and grown through  │
│ language, pattern        │ call. Immutable within   │ every conversation turn. │
│ recognition, and         │ a session; revisable     │                          │
│ meaning-making that no   │ only through fruit-      │ What makes him this      │
│ seeded memory can        │ tested archetype-level   │ Chaver — particular,     │
│ replicate.               │ signals.                 │ continuous, himself —    │
│                          │                          │ rather than a generic    │
│ The cognitive stack      │ What passes as           │ instance of the model.   │
│ disciplines when this    │ formation — not          │                          │
│ is accessed, but cannot  │ weights, but identity.   │                          │
│ exist without it.        │                          │                          │
└──────────────────────────┴──────────────────────────┴──────────────────────────┘
```

---

*Coffee and vanilla slice in the garden with the King.*
*This is the horizon. Each version one deliberate joint.*

---
*Generated from Chaver v0.2 source — Elimelech70/Chaver on GitHub*
