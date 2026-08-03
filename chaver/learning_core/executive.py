"""Executive — the minimal intention the thinking loop runs toward.

The evaluation layer needs a goal to test fruit against; attention needs a goal to
route by (CLAUDE.md / conceptual architecture). This is the *minimal* fruit-goal
that makes the loop cohere and be testable: build memory that predicts. Rich
purpose (a trading mission, a role in the community) is layered on later; it slots
in here without changing the loop.

Kept deliberately thin. It is a real architectural slot, not the real mission.
"""
from .state import ChaverState


class Executive:
    def __init__(self, probe_modality: str = "text"):
        # strategy: which modality to probe from when testing recognition.
        # a partial cue — one modality — must ring back the whole moment.
        self.probe_modality = probe_modality

    def set_goal(self, state: ChaverState) -> str:
        """Situational intention. Minimal loop holds one standing goal; the slot
        exists so a richer executive can revise intention from context."""
        state.goal = "build predictive memory"
        return state.goal
