"""Shared state — read by all concurrent cognitive tasks.

The cognitive stack is not a pipeline. Every layer reads from and writes
to this shared state, concurrently. This is the simultaneity principle
in code form: no messages, no queues — a shared field every layer sees.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from chaver.archetype.model import Archetype
from chaver.working_memory.ringing import WorkingMemory

if TYPE_CHECKING:
    from chaver.hippocampus.binder import Hippocampus
    from chaver.sensory.text_encoder import TextEncoder
    from chaver.sensory.web_search import WebSearch
    from chaver.tools.base import ToolRegistry


@dataclass
class Goal:
    """The current intention. Set by the executive."""

    intention: str
    context: str = ""
    priority: float = 1.0
    set_at: float = field(default_factory=time.time)


@dataclass
class Strategy:
    """The chosen path through the manifold. Set by the strategy layer."""

    approach: str
    steps: list[str] = field(default_factory=list)
    attention_targets: list[str] = field(default_factory=list)
    set_at: float = field(default_factory=time.time)


@dataclass
class EvaluationSignal:
    """A signal emitted by the evaluation monitor.

    Feeds back to strategy (most frequent), behaviour (occasional),
    goal (rare), or archetype (very rare, sanctification-slow).
    """

    layer: str  # "strategy" | "behaviour" | "goal" | "archetype"
    signal: str
    fruit_quality: float  # -1.0 (bad fruit) to 1.0 (good fruit)
    emitted_at: float = field(default_factory=time.time)


@dataclass
class ChaverState:
    """The shared state that all cognitive tasks read."""

    archetype: Archetype
    working_memory: WorkingMemory

    # Memory infrastructure (v0.2). Optional in signature so cognitive
    # tests can construct a bare state; populated at real startup.
    hippocampus: "Hippocampus | None" = None
    text_encoder: "TextEncoder | None" = None

    # Sensory organs (v0.3). web_search is Chaver's eyes — how he sees
    # the world beyond his own memory. Optional so bare-state tests still
    # construct without it.
    web_search: "WebSearch | None" = None

    # Tools (analyst M5): Chaver's hands, outside the cognitive stack. Strategy
    # steps call them; results enter through chaver.tools.field.ingest.
    tools: "ToolRegistry | None" = None

    current_goal: Goal | None = None
    current_strategy: Strategy | None = None
    recent_signals: list[EvaluationSignal] = field(default_factory=list)
    running: bool = True

    # Behaviour modulation — populated by BehaviourModulator from
    # archetype.behavioural_profile, read by every layer.
    wm_decay_multiplier: float = 1.0
    evaluation_gain: float = 1.0
    strategy_abandonment_threshold: float = 0.5

    def record_signal(
        self, signal: EvaluationSignal, max_history: int = 32
    ) -> None:
        """Record an evaluation signal, keeping recent history bounded."""
        self.recent_signals.append(signal)
        if len(self.recent_signals) > max_history:
            self.recent_signals = self.recent_signals[-max_history:]
