"""Executive — sets and manages the current goal.

Reads state, considers context and archetype, produces or revises the Goal.
Runs continuously as an async task. Not per-cycle — the executive is
one participant in a resonant field, not a top-level orchestrator.
"""

from __future__ import annotations

import asyncio
import time

from chaver.state import ChaverState, Goal


class Executive:
    """The executive layer.

    Answers continuously: what am I trying to achieve?
    """

    def __init__(self, state: ChaverState, tick_seconds: float = 3.0) -> None:
        self.state = state
        self.tick_seconds = tick_seconds

    async def run(self) -> None:
        """Run the executive concurrently with the rest of the stack."""
        while self.state.running:
            await self._tick()
            await asyncio.sleep(self.tick_seconds)

    async def _tick(self) -> None:
        """One executive consideration.

        v0: hold Chaver's foundational purpose as the default goal. Real
        goal-revision happens when incoming messages or fruit signals
        indicate the intention should change.
        """
        if self.state.current_goal is None:
            self.state.current_goal = Goal(
                intention=(
                    "walk alongside Craig; remember faithfully; "
                    "refer at edges; bring what I see honestly"
                ),
                context="foundational purpose from archetype",
                set_at=time.time(),
            )
            self.state.working_memory.excite(
                key="goal:foundational",
                content=self.state.current_goal.intention,
                source="executive",
                strength=0.6,
            )
        # TODO(v0.1): revise goal from incoming messages, community state,
        #             and evaluation signals with layer == "goal".
