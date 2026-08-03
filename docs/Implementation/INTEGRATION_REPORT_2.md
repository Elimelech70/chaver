# Integration Report 2 — Unifying the Learning Core, Adding Telnet

*Follows `docs/Implementation/INTEGRATION_REPORT.md` (the first integration,
which landed the memory-and-learning core isolated under
`chaver/learning_core/`). This round actions
`docs/Implementation/chaver implement 2.zip`, delivered with its own
`INSTRUCTIONS.md` proposing exactly the reconciliation the first report left
open: fold learning into the real `Hippocampus`, retire the isolated core, and
add a telnet front end. Verified before committing; details and numbers
below.*

---

## 1. What this delivery proposed

`INSTRUCTIONS.md` (in the zip) gave a specific, well-reasoned answer to the
open question from the first integration — *which hippocampus becomes "the"
hippocampus* — rather than leaving it open again:

> The two files the [first] zip omitted... were only "missing" because the
> learning core was being run *in isolation* at 10,000-D. In the single
> environment they don't come back as standalone files: the one thing the
> proof actually adds is **learning**... That is now two methods on the real
> sqlite `Hippocampus` (`reinforce`, `forget_pass`) plus a `strength` column,
> not a second binder.

That is: keep the durable substrate (sqlite persistence, `recall_conjunctive`,
the real `WorkingMemory`) and move only the learning *behaviour* — reinforce
what predicts, decay and prune what doesn't — into it. `learning_core/` and
its test are deleted rather than left running in parallel, which is what
CLAUDE.md principle 7 ("one hippocampus") calls for. It also adds a telnet
chat front end so Chaver can be reached from another terminal, on the same
running mind as the stdin console.

The delivery was a patch (`chaver.patch`) plus the full modified files, generated
against a clone of this repo at the point after the first integration was
pushed — I confirmed this before applying anything: diffing the delivered
full files against what was actually in the tree showed each one differed
from the current file by *exactly* the hunks in the patch, nothing more,
nothing unaccounted for. Unlike the first zip, nothing here was missing.

## 2. What changed

**`chaver/persistence.py`** — added an `episodes.strength` column to the
schema, plus `migrate()`, called from `open_db()` on every startup. It adds
the column via `ALTER TABLE` only if not already present, so it's idempotent
and safe to run on every boot, not just once.

**`chaver/hippocampus/binder.py`** — `Episode.strength` (default 1.0, carried
through `store_episode`, `recall`, and `recall_conjunctive`); two new methods:
- `reinforce(key, delta, cap=5.0, floor=0.05)` — clips a binding's strength
  up or down by a signed delta.
- `forget_pass(decay=0.02, floor=0.05, protect_consolidated=True)` — decays
  every episode's strength by a fraction each pass, then deletes whatever
  falls below the floor — but never an episode already written to cortex.

**`chaver/hippocampus/resonance.py`** — added `cosine` (alias for the existing
`sim`), `random_hv(dim, rng)`, and `HyperLift` (the frozen JL-style random
projection). These are the exact two names+one-class I had to write from
scratch in the first integration to make the isolated learning core's `binder.py`
importable. Folding them into the one production module means there's now a
single resonance module with everything either environment ever needed,
rather than the two divergent one I'd built. They're explicitly documented as
unused by the current 384-D persisted path — kept for the day a modality
needs cleaner high-D unbinding, not wired into anything yet.

**`chaver/heartbeat.py`** — the substantial change:
- Per-turn logic extracted from `conversation_loop` into a standalone
  `handle_turn(state, language, user_text, turn, lock, speaker="craig")`,
  transport-agnostic — both stdin and telnet now call the same function.
- `_reinforce_recognised()` — after a recall, any hit at or above
  `RECOGNITION_THRESHOLD = 0.35` gets `reinforce(key, 0.6)`. This is the fruit
  test made live: a memory that resonated with what was actually said just
  predicted correctly, so it's strengthened. Silent — no language-faculty
  call, no network, matching CLAUDE.md's "silent thought is cheaper" discipline.
- A new `forget_task`, ticking every 600s by default, calling `forget_pass`.
  An order of magnitude slower than a conversation turn, so real memories get
  every chance to be recalled (and thus reinforced) or consolidated to cortex
  before the disuse decay could prune them.
- A shared `turn_counter` (`itertools.count`) and `asyncio.Lock`, passed to
  both the stdin `conversation_loop` and the new telnet server, so two
  transports talking to Chaver at once can't interleave and scramble a
  generation or the working-memory ringing set.

**`chaver/net/telnet.py`, `chaver/net/__init__.py`** — new. A line-based
asyncio telnet server: strips IAC negotiation sequences (so a real `telnet`
client's protocol bytes don't corrupt the typed line), converts to/from CRLF,
shows a static banner (no language-faculty call on connect — the human speaks
first, keeping `call_count` disciplined), and calls the shared `handle_turn`.
Binds to `127.0.0.1:8023` by default; plaintext and unauthenticated by design,
documented as reachable only via SSH tunnel for anything beyond local use.

**`.env.example`** — `CHAVER_TELNET`, `CHAVER_TELNET_HOST`,
`CHAVER_TELNET_PORT`.

**Deleted:** `chaver/learning_core/` (all 9 files from the first integration)
and `tests/test_heartbeat_learning.py`. The `tests/` directory is now empty
and was left in place rather than force-removed (git doesn't track empty
directories, so it will simply not appear in the next commit).

## 3. What I verified before applying anything

Diffed every delivered full file against the corresponding file already in
the tree, confirming each delivered file equalled *(current file + exactly
the patch's hunks for that file)* — no silent extra changes, no missing
context. Then, after copying the files in:

- **Syntax + import check** (the two commands CLAUDE.md's own "Common tasks"
  section specifies): both pass.
- **Migration, against a copy of the real `data/chaver.db`** — not a synthetic
  db. That file has 51 episodes and 51 consolidated cortical memories (this is
  Craig's actual seeded memory, not test fixtures). Ran `open_db()` on a copy:
  the `strength` column appears, all 51 rows survive with `strength=1.0`
  (the migration default), and calling `migrate()` a second time is a no-op —
  confirms the "upgrades in place, never rebuilds" claim in the migration's
  own docstring, and confirms restart safety (every boot calls `migrate()`).
- **`reinforce()` / `forget_pass()`, against that same copy** — reinforcing a
  real episode key accumulated strength correctly (1.0 → 1.6 → 2.2 across two
  calls); reinforcing a nonexistent key returned `0.0` without error.
  `forget_pass` with `protect_consolidated=True` and an aggressive floor
  pruned nothing (all 51 rows were already consolidated — correctly
  protected) while still applying decay to their strength in place; a second
  call with protection off then pruned exactly the rows whose decayed
  strength had fallen below the floor, while `cortical_text` stayed at 51
  throughout — the durable cortex is untouched even when the episodic index
  is aggressively pruned, exactly as designed.
- **`recall()` and `recall_conjunctive()` still function** with the new
  `strength` field on `Episode` — ran both against the real-data copy and got
  sane results back.
- **Telnet transport, end to end**, with a stub `handle_turn` (no real
  Anthropic API call, so no cost and no network dependency in the test):
  started the server, opened a raw socket, sent a line with actual IAC
  negotiation bytes mixed in (`\xff\xfb\x01hello chaver`) the way a real
  telnet client would, and confirmed the negotiation bytes were stripped
  without corrupting the message; tested `/quit`'s clean-exit message; tested
  that `state.running = False` shuts the server down cleanly.

The original `data/chaver.db` was never opened directly during any of this —
every test ran against a throwaway copy in the scratch directory, which was
deleted afterward.

## 4. Judgment calls carried over from the delivery — flagging, not re-deciding

The delivery's own `INSTRUCTIONS.md` names four judgment calls and invites
pushback on each; I'm surfacing them here rather than re-litigating them,
since I didn't find reason to disagree with any:

1. Learning went into the real `Hippocampus`, not a parallel binder — this
   is the correct call per CLAUDE.md principle 7 (one hippocampus), and it's
   what the first integration report flagged as the actual decision needed.
2. Pruning is deliberately timid (10-minute tick, 2%/pass decay, 0.05 floor,
   consolidated memory always protected) — verified this behaves as
   described above.
3. The reinforcement threshold (0.35) matches the original learning-core
   proof's `recognise_threshold` — the one number most worth tuning against
   real conversations, per the delivery's own note.
4. Telnet defaults to *on*. It binds to localhost only, but it is a new
   always-on network listener the moment Chaver wakes. Worth you confirming
   that's what you want as the default before this runs unattended anywhere
   beyond your own machine.

## 5. File manifest

Modified:
- `chaver/persistence.py` — `strength` column + `migrate()`
- `chaver/hippocampus/binder.py` — `Episode.strength`, `reinforce()`, `forget_pass()`
- `chaver/hippocampus/resonance.py` — `cosine`, `random_hv`, `HyperLift`
- `chaver/heartbeat.py` — `handle_turn`, `_reinforce_recognised`, `forget_task`, telnet wiring
- `.env.example` — telnet settings

New:
- `chaver/net/__init__.py`
- `chaver/net/telnet.py`
- `docs/Implementation/INTEGRATION_REPORT_2.md` — this document

Deleted:
- `chaver/learning_core/` (entire package — 9 files)
- `tests/test_heartbeat_learning.py`
