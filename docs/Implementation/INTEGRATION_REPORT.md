# Integration Report — Chaver Implementation.zip (Memory & Learning Core)

*Written after pulling `origin/main` (commit `8b60f2d`, "new implementation") and
actioning `docs/Implementation/Chaver Implementation.zip`. Read alongside
`docs/Implementation/CHAVER_BUILD_GUIDE.md` — that document explains the design
intent; this one records what actually happened bringing it into the tree.*

---

## 1. What arrived

The zip contained 7 files: `CHAVER_BUILD_GUIDE.md` plus six Python modules —
`state.py`, `executive.py`, `evaluation.py`, `heartbeat.py`, `binder.py`, and
`test_heartbeat_learning.py`. Together they're a **standalone proof that a
resonance-binding hippocampus can learn**: a synthetic "moment" (three modality
vectors) recurs among noise; the agent perceives it, tries to recall the whole
from one modality as a cue, checks whether the recall predicted correctly
(the "minimal fruit" — predictive recognition), and reinforces bindings that
predicted well while letting unreinforced ones decay and get pruned.

This is a different, narrower thing than the `resonance-binding-
implementation-v1.md` work already in the tree (the doc/demo closed in the
previous session). That work proved the VSA algebra in isolation
(`binding_demo.py`) and wired one query — conjunctive recall — into the
production `Hippocampus`. This delivery is a **second, self-contained agent
loop**: its own state, its own executive/evaluation, its own hippocampus
variant, its own heartbeat — built to demonstrate learning (reinforcement +
forgetting), not just binding.

## 2. Two problems before any of it could run

**The zip was incomplete relative to its own inventory.** `CHAVER_BUILD_GUIDE.md`
§2 lists nine files as "tested" or "built," including `hippocampus/resonance.py`,
`hippocampus/loop.py`, `working_memory.py`, and `language/faculty.py`. Only six
files were actually in the archive. `binder.py` and `heartbeat.py` both import
names — `HyperLift`, `random_hv`, `bind`, `unbind`, `bundle`, `cosine`,
`cleanup` from a `resonance` module, and `RingingWorkingMemory` with
`.excite(key, content, activation=...)` / `.decay_tick(multiplier)` from a
`working_memory` module — that exist nowhere in the delivery. Without those two
files nothing imports, let alone runs.

**The intended file paths collide with production code.** The guide's own file
table places these at `chaver/state.py`, `chaver/heartbeat.py`,
`chaver/working_memory.py`, `chaver/hippocampus/binder.py`, and
`chaver/hippocampus/resonance.py`. Every one of those paths is already live:
`chaver/state.py` (the real `ChaverState`, archetype + hippocampus + working
memory), `chaver/heartbeat.py` (`chaver_awake`, the actual running agent),
`chaver/working_memory/ringing.py` (a package, so a flat `working_memory.py`
can't coexist with it at all), and `chaver/hippocampus/{binder,resonance}.py`
(the `Hippocampus` and VSA algebra from the prior session, including the
`recall_conjunctive` query already wired to real sqlite data). Dropping the zip
in at those paths would have silently overwritten a running agent's memory
layer with an in-RAM synthetic-vector proof.

The guide itself anticipates exactly this, in its build order: *"Install it
alongside; do not overwrite the working binder... Swap the wiring only once the
loop test passes in-tree."* That sentence is the instruction I followed.

## 3. What I did

**Isolated the delivery under `chaver/learning_core/`,** mirroring the zip's
intended relative-import structure (`heartbeat.py` imports `.evaluation`,
`.executive`, `.hippocampus.binder`, `.hippocampus.resonance`, `.state`,
`.working_memory` — all one level, all satisfied by this layout) so the
delivered files could be placed **unmodified**:

```
chaver/learning_core/
├── __init__.py
├── state.py            (unmodified from zip)
├── executive.py         (unmodified from zip)
├── evaluation.py         (unmodified from zip)
├── heartbeat.py         (unmodified from zip)
├── working_memory.py     (written — see below)
└── hippocampus/
    ├── __init__.py
    ├── binder.py          (unmodified from zip)
    └── resonance.py       (written — see below)
```

Nothing under `chaver/` outside `learning_core/` was touched. `chaver/state.py`,
`chaver/heartbeat.py`, `chaver/working_memory/`, and
`chaver/hippocampus/{binder,resonance}.py` are exactly as they were.

**Wrote the two missing modules to the API contract the delivered files already
assume**, rather than inventing new design:

- `chaver/learning_core/hippocampus/resonance.py` — `bind`/`unbind`/`bundle`
  are the same HRR circular-convolution algebra as the production
  `chaver/hippocampus/resonance.py` (consistent with the algebra already
  proven in `binding_demo.py`), but this module's `random_hv(dim, rng)` takes
  an explicit generator rather than being name-keyed, because that's how
  `binder.py::_role()` already calls it (`rz.random_hv(self.bind_dim, r)` with
  a locally-seeded `r`). The one genuinely new piece is `HyperLift`: a frozen,
  seeded Gaussian random projection (scaled `1/√embed_dim`, standard
  Johnson–Lindenstrauss construction) that lifts each modality's native
  384-dim embedding up into the 10,000-dim binding space the build guide's §3
  calls for. It's unlearned and re-derives identically from its seed every
  time, so nothing needs to persist the projection matrix itself.
- `chaver/learning_core/working_memory.py` — `RingingWorkingMemory`: an
  in-RAM dict of ringing patterns, capacity-bounded by evicting the weakest,
  decaying by elapsed time since last excitation. Matches the call sites in
  the delivered `heartbeat.py` exactly (`excite(key, content, activation=1.0)`,
  `decay_tick(multiplier)`). Deliberately separate from the production
  `WorkingMemory` (CLAUDE.md principle 4: a ringing set, not a database) —
  reconciling the two is flagged as future work, not done here (§5 below).

**Relocated the test** to `tests/test_heartbeat_learning.py`, repointed at
`chaver.learning_core.*` instead of the flat `chaver.*` the zip's version used
(which would have collided the same way). The test's logic is byte-for-byte
the delivered version — only the import lines changed.

## 4. Result — the acceptance test

Ran `PYTHONPATH=/root/chaver .venv/bin/python3 tests/test_heartbeat_learning.py`.
Output:

```
    window  R_recognised  noise_FP
     early          0.99      0.00
      late          1.00      0.00

R recognised late: 1.00 | noise false-positive late: 0.00
store peak 175 -> late 167 (plateau = pruning works)

LEARNING DEMONSTRATED
```

All three of the build guide's §6 success criteria hold: R-recognition ends at
1.00 (recognised even higher than early — starts at 0.99 because the
`recognise_threshold` of 0.35 is loose enough that even before reinforcement
the correct completion usually clears it; what changes over the run is
strength, visible in the `r_strength` trace climbing from 1.0 to a sustained
~5.0 ceiling), noise false-positives stay at 0.00 throughout, and the episode
store plateaus (peaks at 175, settles to 167 as `forget_pass` prunes
unreinforced noise) rather than growing linearly with tick count. I added an
`assert learned` at the end of the relocated test so it fails loudly (nonzero
exit) if a future change regresses any of these — the delivered version only
printed a message.

I also re-ran `binding_demo.py` and the production import check
(`from chaver.heartbeat import chaver_awake`) afterward to confirm this work
left the existing tree undisturbed — both still pass.

## 5. What this closes, and what's still a decision for Craig

**Closed:** the delivered learning core runs, and its own acceptance test
passes on the actual numbers it was designed to produce. The two files missing
from the zip are filled in to the contract the rest of the delivery already
assumes, not redesigned. The claim in `CHAVER_BUILD_GUIDE.md` §0 — "everything
here is built and tested" — is now true in the sense that it's runnable and
its test passes; it was not true as delivered, since two required files were
absent.

**Not done, and deliberately left as a decision rather than a default:**

The build guide's §4 "build order" describes four further reconciliation
steps — install alongside (done), wire persistence, reconcile working memory,
register the heartbeat (fold into `chaver.heartbeat` alongside the existing
seven cognitive tasks) — each of which means *replacing or merging into*
running production code:

- `ResonanceHippocampus` (in-RAM, `bind_dim=10,000`, learns via
  reinforce/forget) vs. the production `Hippocampus` (sqlite-backed,
  `dimension=384` native, no reinforcement/decay yet, but already has
  `recall_conjunctive` reading real consolidated memory). These are not
  drop-in replacements for each other — one persists, one doesn't; one learns,
  one doesn't; they bind at different widths.
- Two `ChaverState` dataclasses with almost nothing in common (the production
  one carries `archetype`, `hippocampus`, `text_encoder`, `current_goal`,
  `recent_signals`; the learning-core one carries `goal`, `behaviour`, `tick`,
  `recall_attempts`). Merging them is a real design choice about which fields
  the production cognitive stack (`Attention`, `StrategyLayer`, etc., none of
  which the learning core's minimal `Executive`/`Evaluation` know about) would
  need.
- Two working-memory implementations with the guide's own flagged
  method-name mismatch (`decay_tick()` vs `decay()`) still unresolved.

None of this is a small refactor — it's the difference between "an isolated
proof that reinforcement learning works on a synthetic stream" and "swap
Chaver's live memory for it." Per CLAUDE.md's closing instruction and the
build guide's own phased approach ("swap the wiring only once the loop test
passes in-tree" — which it now does), I stopped at the point where the proof
runs and is verified, rather than making the wiring decision unilaterally.
The concrete next step, if you want it: pick which of the two hippocampi (or
what merge of them) becomes *the* hippocampus, since CLAUDE.md principle 7 is
one hippocampus, not two running side by side indefinitely.

## 6. File manifest

New, isolated (no production files touched):
- `chaver/learning_core/__init__.py`
- `chaver/learning_core/state.py` — from zip, unmodified
- `chaver/learning_core/executive.py` — from zip, unmodified
- `chaver/learning_core/evaluation.py` — from zip, unmodified
- `chaver/learning_core/heartbeat.py` — from zip, unmodified
- `chaver/learning_core/working_memory.py` — written to fill the zip's gap
- `chaver/learning_core/hippocampus/__init__.py`
- `chaver/learning_core/hippocampus/binder.py` — from zip, unmodified
- `chaver/learning_core/hippocampus/resonance.py` — written to fill the zip's gap
- `tests/test_heartbeat_learning.py` — from zip, imports repointed, `assert` added
- `docs/Implementation/INTEGRATION_REPORT.md` — this document
