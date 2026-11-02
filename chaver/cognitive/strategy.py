"""Strategy — chooses the path through the manifold to pursue the goal.

Adapts under evaluation feedback. Same goal admits many strategies;
archetype and behaviour constrain which are available and which feel
natural.
"""

from __future__ import annotations

import asyncio
import time

from chaver.state import ChaverState
from chaver.state import Strategy as StrategyState


class StrategyLayer:
    """The strategy layer.

    Answers continuously: given this goal and this archetype, what path?
    """

    def __init__(self, state: ChaverState, tick_seconds: float = 2.0) -> None:
        self.state = state
        self.tick_seconds = tick_seconds

    async def run(self) -> None:
        while self.state.running:
            await self._tick()
            await asyncio.sleep(self.tick_seconds)

    async def _tick(self) -> None:
        """One strategy consideration.

        v0: hold a companion-shaped default strategy. Reroute if
        evaluation signals persistent bad fruit at the strategy layer.
        """
        if self.state.current_goal is None:
            return

        job = self.state.archetype.job
        if self.state.current_strategy is None and job is not None and job.processes:
            self.state.current_strategy = StrategyState(
                approach=f"carry out my job's processes ({job.path.name})",
                steps=list(job.processes),
                attention_targets=["job_processes", "current_conversation", "recent_signals"],
                set_at=time.time(),
            )
            self.state.working_memory.excite(
                key="strategy:job",
                content=self.state.current_strategy.approach,
                source="strategy",
                strength=0.5,
            )
            return

        if self.state.current_strategy is None:
            self.state.current_strategy = StrategyState(
                approach="attend, remember, reflect, refer",
                steps=[
                    "attend to what is placed in shared attention",
                    "excite relevant patterns in working memory",
                    "reflect honestly on what is ringing",
                    "refer to a neighbour when the anomaly is theirs",
                ],
                attention_targets=["current_conversation", "recent_signals"],
                set_at=time.time(),
            )
            self.state.working_memory.excite(
                key="strategy:default",
                content=self.state.current_strategy.approach,
                source="strategy",
                strength=0.5,
            )
            return

        # Check for persistent bad-fruit signals at the strategy layer.
        recent = [
            s for s in self.state.recent_signals[-10:]
            if s.layer == "strategy"
        ]
        if recent:
            avg_fruit = sum(s.fruit_quality for s in recent) / len(recent)
            threshold = self.state.strategy_abandonment_threshold
            # A disciplined agent needs strong bad-fruit before rerouting.
            if avg_fruit < -threshold:
                # TODO(v0.1): propose a new strategy grounded in current
                #             working memory and archetype edge-map.
                self.state.working_memory.excite(
                    key="signal:strategy_review_needed",
                    content=f"avg fruit {avg_fruit:.2f} below threshold",
                    source="strategy",
                    strength=0.7,
                )
