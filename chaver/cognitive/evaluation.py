"""Evaluation — the continuous monitor.

Runs in parallel with everything else. Asks: is fruit forming? Is the
strategy converging? Has the goal been overtaken? Is behaviour appropriate?

Gain is behaviour-dependent. A cautious agent flags on small signals;
a bold agent needs strong disconfirmation before rerouting.

Feeds back in priority: strategy (most frequent) → behaviour (occasional)
→ goal (rare) → archetype (very rare, sanctification-slow).
"""

from __future__ import annotations

import asyncio

from chaver.state import ChaverState, EvaluationSignal


class Evaluation:
    """The continuous evaluation monitor."""

    def __init__(self, state: ChaverState, tick_seconds: float = 4.0) -> None:
        self.state = state
        self.tick_seconds = tick_seconds

    async def run(self) -> None:
        while self.state.running:
            self._tick()
            await asyncio.sleep(self.tick_seconds)

    def _tick(self) -> None:
        """One evaluation pass.

        v0: monitor whether working memory is genuinely engaging with the
        current strategy. If WM is empty or stale, that is a mild bad-fruit
        signal at the strategy layer — attention isn't finding purchase.

        Fruit-testing at scale will require real outcomes to grade against
        (referrals that landed, decisions that bore good/bad fruit, etc.).
        v0 is the skeleton of the reflex.
        """
        wm_size = len(self.state.working_memory)

        # Very small working memory over time is a soft signal that
        # attention isn't finding purchase — but not certain bad fruit.
        if wm_size < 2:
            signal = EvaluationSignal(
                layer="strategy",
                signal=(
                    f"working memory sparse ({wm_size} patterns) — "
                    "attention may not be finding purchase"
                ),
                fruit_quality=-0.2 * self.state.evaluation_gain,
            )
            self.state.record_signal(signal)

        # TODO(v0.1): fruit-testing against real outcomes — referrals,
        #             decisions, honest reflection against archetype.
