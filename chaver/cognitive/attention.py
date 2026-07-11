"""Attention — routes excitation.

Determines what is currently sampled and what patterns get excited in
working memory. Influenced by goal, strategy, behaviour, novelty,
salience, urgency.

v0: reads current strategy's attention_targets and refreshes their
excitation in working memory. When sensors come online, attention will
also decide which sensory streams to sample.
"""

from __future__ import annotations

import asyncio

from chaver.state import ChaverState


class Attention:
    """The attention router."""

    def __init__(self, state: ChaverState, tick_seconds: float = 1.5) -> None:
        self.state = state
        self.tick_seconds = tick_seconds

    async def run(self) -> None:
        while self.state.running:
            self._tick()
            await asyncio.sleep(self.tick_seconds)

    def _tick(self) -> None:
        """One attention cycle.

        Refresh excitation on the strategy's attention targets. When those
        targets exist as patterns in working memory, their activation is
        renewed. This keeps the intentional focus alive against decay.
        """
        strategy = self.state.current_strategy
        if strategy is None:
            return

        for target in strategy.attention_targets:
            # Nudge existing patterns whose keys or content mention the target.
            for pattern in self.state.working_memory.current():
                if target in pattern.key or target in str(pattern.content):
                    self.state.working_memory.excite(
                        key=pattern.key,
                        content=pattern.content,
                        source=pattern.source,
                        strength=0.15,
                    )
        # TODO(v0.1): when sensors come online, decide which streams to
        #             sample this cycle based on strategy + salience.
