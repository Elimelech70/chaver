"""Evaluation — the continuous fruit-test (CLAUDE.md: fruit tests everyone).

The minimal fruit for a memory-and-learning proof is *predictive recognition*: a
binding bore fruit if, cued by a fragment, it completed to what the moment
actually was. Recognised-from-partial is positive fruit; a confident wrong
completion is negative. Fruit becomes a learning delta the hippocampus applies —
proven bindings strengthen, misleading ones weaken, unused ones fade.

Gain is behaviour-modulated: a cautious agent (high gain) treats small
disconfirmations as significant; a bold agent (low gain) needs strong
disconfirmation to reroute.
"""
from dataclasses import dataclass


@dataclass
class Evaluation:
    recognise_threshold: float = 0.35     # cosine above which a recall counts as a hit
    reward: float = 0.6                   # strength delta on a confirmed recognition
    penalty: float = 0.3                  # strength delta on a confident miss

    def fruit(self, similarity: float, gain: float = 1.0) -> tuple[bool, float, float]:
        """Return (recognised, signed_fruit, strength_delta).
        similarity: cosine of the recalled episode's pattern to the actual moment."""
        recognised = similarity >= self.recognise_threshold
        if recognised:
            signed = similarity
            delta = self.reward * gain
        else:
            # a confident-but-wrong completion is the costly case; a weak,
            # correctly-uncertain recall barely penalised.
            signed = -(max(0.0, similarity))
            delta = -self.penalty * gain * max(0.0, similarity)
        return recognised, signed, delta
