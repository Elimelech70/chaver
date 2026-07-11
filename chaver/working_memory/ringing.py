"""Working Memory — the currently-ringing set of resonance shapes.

Not a database. Not a queried store. The set of patterns currently under
sustained excitation. Held in RAM. Read by every cognitive layer
concurrently.

Contents decay unless re-excited. Capacity is metabolically bounded.
Behaviour modulates decay rate and capacity — a disciplined agent has
slower decay (patterns persist); a creative agent has higher decay
(patterns cycle faster to admit novelty).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RingingPattern:
    """A pattern currently ringing in working memory.

    Not a stored memory — an active excitation. Activation decays over
    time unless the pattern is re-excited.
    """

    key: str  # unique identifier
    content: Any  # pattern content (multimodal in later versions)
    activation: float  # current strength (0.0 - 1.0)
    excited_at: float  # timestamp of last excitation
    source: str  # where this pattern came from
    metadata: dict = field(default_factory=dict)


class WorkingMemory:
    """The currently-ringing set of resonance shapes.

    Not the whole mind — what is currently active in the mind. Every
    cognitive layer reads from here and writes to here.
    """

    def __init__(
        self,
        capacity: int = 12,
        base_decay_rate: float = 0.02,
    ) -> None:
        """Initialise working memory.

        Args:
            capacity: Maximum number of patterns held. Behaviour modulates.
            base_decay_rate: Activation loss per second at neutral behaviour.
        """
        self._patterns: dict[str, RingingPattern] = {}
        self.capacity = capacity
        self.base_decay_rate = base_decay_rate

    def excite(
        self,
        key: str,
        content: Any,
        source: str,
        strength: float = 1.0,
        metadata: dict | None = None,
    ) -> None:
        """Excite (or re-excite) a pattern in working memory.

        If the pattern exists, its activation is raised. If it doesn't,
        it is added. If capacity is exceeded, the weakest pattern is
        evicted.
        """
        now = time.time()
        if key in self._patterns:
            pattern = self._patterns[key]
            pattern.activation = min(1.0, pattern.activation + strength)
            pattern.excited_at = now
            if metadata:
                pattern.metadata.update(metadata)
        else:
            if len(self._patterns) >= self.capacity:
                self._evict_weakest()
            self._patterns[key] = RingingPattern(
                key=key,
                content=content,
                activation=min(1.0, strength),
                excited_at=now,
                source=source,
                metadata=metadata or {},
            )

    def decay(self, decay_multiplier: float = 1.0) -> None:
        """Apply time-based decay to all patterns.

        Args:
            decay_multiplier: Behaviour-modulated multiplier. Disciplined
                agents have lower multiplier (patterns persist); creative
                agents have higher (patterns cycle faster).
        """
        now = time.time()
        expired_keys: list[str] = []
        for pattern in self._patterns.values():
            elapsed = now - pattern.excited_at
            loss = self.base_decay_rate * elapsed * decay_multiplier
            pattern.activation = max(0.0, pattern.activation - loss)
            pattern.excited_at = now  # reset elapsed baseline
            if pattern.activation <= 0.01:
                expired_keys.append(pattern.key)
        for key in expired_keys:
            del self._patterns[key]

    def current(self) -> list[RingingPattern]:
        """Return the currently-ringing set, ordered by activation."""
        return sorted(
            self._patterns.values(),
            key=lambda p: p.activation,
            reverse=True,
        )

    def summary(self, max_items: int = 12) -> str:
        """Human-readable summary of what is currently ringing.

        Passed to the language faculty as wm_context when Chaver speaks,
        so his words emerge grounded in his current state.
        """
        patterns = self.current()[:max_items]
        if not patterns:
            return "(nothing currently ringing)"
        lines = [
            f"- [{p.activation:.2f}] {p.key} (from {p.source}): "
            f"{str(p.content)[:200]}"
            for p in patterns
        ]
        return "\n".join(lines)

    def __len__(self) -> int:
        return len(self._patterns)

    def _evict_weakest(self) -> None:
        weakest = min(self._patterns.values(), key=lambda p: p.activation)
        del self._patterns[weakest.key]
