"""RingingWorkingMemory — in-RAM ringing set for the learning core.

NOT part of the delivered zip. CHAVER_BUILD_GUIDE.md §2 lists
`working_memory.py` / `RingingWorkingMemory` as "tested" and §4 build order
step 3 even flags a specific method-name reconciliation to do against it
("this uses decay_tick(), docs say decay()") — but no such file shipped in
Chaver Implementation.zip, and heartbeat.py imports `RingingWorkingMemory`
from `.working_memory` and calls `.excite(key, content, activation=...)` and
`.decay_tick(multiplier)` on it. Written here to that exact call contract.

Deliberately minimal and separate from chaver/working_memory/ringing.py (the
production WorkingMemory) — CLAUDE.md principle 4: a ringing set, not a
database; no query interface beyond "what's currently ringing." Reconciling
the two into one (per the build guide's step 3) is a wiring decision, not
made here — see docs/Implementation/INTEGRATION_REPORT.md.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _Ringing:
    key: str
    content: Any
    activation: float
    excited_at: float = field(default_factory=time.time)


class RingingWorkingMemory:
    """The currently-ringing set. In RAM, decays unless re-excited, capacity
    bounded by eviction of the weakest pattern — no SQL-style query surface."""

    def __init__(self, capacity: int = 16, base_decay_rate: float = 0.05):
        self._items: dict[str, _Ringing] = {}
        self.capacity = capacity
        self.base_decay_rate = base_decay_rate

    def excite(self, key: str, content: Any, activation: float = 1.0) -> None:
        now = time.time()
        if key in self._items:
            item = self._items[key]
            item.activation = min(1.0, item.activation + activation)
            item.content = content
            item.excited_at = now
            return
        if len(self._items) >= self.capacity:
            weakest = min(self._items.values(), key=lambda p: p.activation)
            del self._items[weakest.key]
        self._items[key] = _Ringing(
            key=key, content=content, activation=min(1.0, activation)
        )

    def decay_tick(self, multiplier: float = 1.0) -> None:
        now = time.time()
        dead = []
        for item in self._items.values():
            elapsed = now - item.excited_at
            item.activation -= self.base_decay_rate * multiplier * elapsed
            item.excited_at = now
            if item.activation <= 0.01:
                dead.append(item.key)
        for k in dead:
            del self._items[k]

    def current(self) -> list[_Ringing]:
        return sorted(self._items.values(), key=lambda p: p.activation, reverse=True)

    def __len__(self) -> int:
        return len(self._items)
