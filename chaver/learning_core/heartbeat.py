"""Heartbeat — the maintained loop that makes Chaver think.

Continuity is not the saved file; it is this loop running (Architecture Imperative
§7). The cognitive work runs as concurrent asyncio tasks reading shared
ChaverState (CLAUDE.md): a cognition task (perceive -> recall -> evaluate -> learn
-> bind) and a housekeeping task (consolidate, forget, decay), propagating
simultaneously rather than down a pipeline.

The minimal fruit is predictive recognition: cued by a fragment, does memory
complete to what the moment actually is? Recurring structure gets recognised and
reinforced; noise is seen once and fades. No market, no LLM, no GPU — this is the
memory-and-learning core, and it runs on a CPU laptop.

Fuller decomposition (a separate concurrent evaluation task; WM as the structured
cue source) is the next step and is flagged inline. This is the minimal loop that
demonstrably thinks toward a minimal fruit.
"""
import asyncio
import logging
from collections.abc import Callable

from .evaluation import Evaluation
from .executive import Executive
from .hippocampus import resonance as rz
from .hippocampus.binder import ResonanceHippocampus
from .state import ChaverState
from .working_memory import RingingWorkingMemory

log = logging.getLogger("chaver.heartbeat")

# a source yields one moment: (modality -> native embedding, a label for metrics)
Source = Callable[[], tuple[dict[str, "object"], str]]


class Chaver:
    def __init__(self, hippocampus: ResonanceHippocampus, wm: RingingWorkingMemory,
                 executive: Executive, evaluation: Evaluation, state: ChaverState,
                 source: Source, tick_seconds: float = 0.001,
                 housekeeping_every: int = 10, max_ticks: int | None = None,
                 forget_decay: float = 0.05):
        self.hc = hippocampus
        self.wm = wm
        self.executive = executive
        self.evaluation = evaluation
        self.state = state
        self.source = source
        self.tick_seconds = tick_seconds
        self.housekeeping_every = housekeeping_every
        self.max_ticks = max_ticks
        self.forget_decay = forget_decay
        self._novel = 0
        self._r_key: str | None = None            # first-stored recurring episode (metrics)
        self.history: list[dict] = []
        self.events: list[tuple[str, bool]] = []  # (label, recognised) per tick

    # -- cognition: perceive, recall, evaluate, learn, bind ----------------
    def _cognition_tick(self) -> None:
        moment, label = self.source()
        self.executive.set_goal(self.state)
        probe_mod = self.executive.probe_modality

        # perception rings working memory (salience); its decay is metabolic
        self.wm.excite(f"perc:{probe_mod}", moment[probe_mod], activation=1.0)

        # recall from a partial cue: one modality must ring back the whole moment
        hits = self.hc.recall({probe_mod: moment[probe_mod]}, top_k=1)

        # the actual moment's joint pattern, to score what recall completed to
        transient = self.hc.bind(moment, key="__probe__").pattern
        self.hc._episodes.pop("__probe__", None)

        similarity, recalled_key = 0.0, None
        if hits:
            recalled_key = hits[0][0]
            recalled = self.hc._episodes.get(recalled_key)
            if recalled is not None:
                similarity = rz.cosine(transient, recalled.pattern)

        recognised, signed, delta = self.evaluation.fruit(
            similarity, gain=self.state.behaviour.evaluation_gain)
        self.state.recall_attempts += 1
        self.state.last_fruit = signed
        self.events.append((label, recognised))    # (what it was, did memory catch it)

        if recognised and recalled_key is not None:
            # fruit: memory predicted the moment — strengthen that binding
            self.state.recall_hits += 1
            self.state.last_recall = recalled_key
            self.hc.reinforce(recalled_key, delta)
        else:
            # novel moment — bind it so it can be recognised next time
            self._novel += 1
            key = f"ep{self._novel}"
            self.hc.bind(moment, key=key)
            if label == "R" and self._r_key is None:
                self._r_key = key

        self.state.tick += 1

    # -- housekeeping: consolidate, forget, decay --------------------------
    def _housekeeping_tick(self) -> None:
        self.hc.forget_pass(decay=self.forget_decay)    # disuse decay + prune noise
        self.hc.consolidate(max_age_seconds=0.0, min_activation=0.0)
        self.wm.decay_tick(self.state.behaviour.wm_decay_multiplier)

    def _snapshot(self) -> None:
        r_strength = 0.0
        if self._r_key and self._r_key in self.hc._episodes:
            r_strength = self.hc._episodes[self._r_key].strength
        self.history.append({
            "tick": self.state.tick,
            "episodes": len(self.hc._episodes),
            "r_strength": round(r_strength, 3),
            "hit_rate": round(self.state.hit_rate, 3),
        })

    # -- concurrent runtime ------------------------------------------------
    async def _cognition_task(self) -> None:
        while self.state.running:
            try:
                self._cognition_tick()
                if self.state.tick % self.housekeeping_every == 0:
                    self._snapshot()
            except Exception:  # noqa: BLE001 — the heart keeps beating
                log.exception("cognition tick failed; continuing")
            if self.max_ticks and self.state.tick >= self.max_ticks:
                self.state.running = False
            await asyncio.sleep(self.tick_seconds)

    async def _housekeeping_task(self) -> None:
        last = 0
        while self.state.running:
            try:
                if self.state.tick - last >= self.housekeeping_every:
                    self._housekeeping_tick()
                    last = self.state.tick
            except Exception:  # noqa: BLE001
                log.exception("housekeeping tick failed; continuing")
            await asyncio.sleep(self.tick_seconds * 2)

    async def run(self) -> None:
        """Bring him awake: concurrent tasks over shared state."""
        await asyncio.gather(self._cognition_task(), self._housekeeping_task())
