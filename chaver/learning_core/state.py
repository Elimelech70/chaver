"""ChaverState — the shared blackboard the concurrent cognitive tasks read.

The cognitive stack does not pass messages down a pipeline; every layer reads and
writes this one shared state, simultaneously, under the heartbeat's asyncio.gather
(CLAUDE.md: the stack ordering in diagrams is conceptual; the mechanism is
simultaneous propagation). Keep this a plain dataclass of typed fields — no
methods that do cognition, no query interface. It is the field they all ring in.
"""
from dataclasses import dataclass, field


@dataclass
class Behaviour:
    """Sideways modulators. Not a step in the loop — parameters every layer reads
    (CLAUDE.md). A disciplined agent decays slower; a cautious agent evaluates at
    higher gain."""
    wm_decay_multiplier: float = 1.0
    evaluation_gain: float = 1.0
    strategy_abandonment_threshold: float = 0.5


@dataclass
class ChaverState:
    goal: str = "build predictive memory"      # the minimal fruit-goal (see executive)
    behaviour: Behaviour = field(default_factory=Behaviour)
    tick: int = 0
    last_recall: str | None = None              # episode key the binder last completed to
    last_fruit: float = 0.0                     # signed fruit of the last evaluation
    recall_attempts: int = 0
    recall_hits: int = 0
    running: bool = True

    @property
    def hit_rate(self) -> float:
        return self.recall_hits / self.recall_attempts if self.recall_attempts else 0.0
