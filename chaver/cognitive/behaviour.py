"""Behaviour Modulator — sideways to the loop, colouring every step.

Behaviour is not a step in the pipeline. It is a parameter set that every
other layer reads: working-memory decay rate, evaluation gain, strategy
abandonment threshold, novelty bias.

Behaviour is trained, not configured. In v0 it is read directly from
archetype.behavioural_profile. Later versions will retune it slowly
through fruit-tested experience.
"""

from __future__ import annotations

import asyncio

from chaver.state import ChaverState


class BehaviourModulator:
    """Applies behavioural parameters to shared state.

    Reads archetype.behavioural_profile and populates the modulation
    fields on ChaverState that every other layer consults.
    """

    def __init__(self, state: ChaverState, tick_seconds: float = 5.0) -> None:
        self.state = state
        self.tick_seconds = tick_seconds

    async def run(self) -> None:
        while self.state.running:
            self._apply()
            await asyncio.sleep(self.tick_seconds)

    def _apply(self) -> None:
        """Translate archetype behavioural profile into modulation parameters.

        Discipline lowers WM decay (patterns persist longer).
        Caution raises evaluation gain (small signals trigger review).
        Discipline raises strategy abandonment threshold (harder to reroute).
        """
        profile = self.state.archetype.behavioural_profile

        # Higher discipline → slower decay (multiplier below 1.0).
        self.state.wm_decay_multiplier = max(0.2, 1.0 - profile.discipline * 0.6)

        # Higher caution → higher evaluation gain.
        self.state.evaluation_gain = 0.5 + profile.caution * 1.0

        # Higher discipline → higher threshold for strategy abandonment.
        self.state.strategy_abandonment_threshold = 0.3 + profile.discipline * 0.5
