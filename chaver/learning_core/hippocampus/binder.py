"""ResonanceHippocampus — the one relational binder, on the resonance substrate.

This is the resonance implementation of the hippocampus the topology names:
bind() forms the joint index from co-active modality vectors, recall() completes
a whole episode from a partial cue, consolidate() writes the episodic fillers out
to the per-modality cortical stores (slow), and query_role() answers structured
questions by unbinding a role and cleaning up against cortex.

The hippocampus holds the *index*; the cortex holds the fragments. Recall is
unbind-then-settle-onto-cortex, never a stored (subject, relation) -> object row.

Conventions (CLAUDE.md): float32 L2-normalised vectors; dataclasses for state;
no cognitive call crosses the network; errors in the runtime are logged and
swallowed by the caller, not raised out of a heartbeat.
"""
from __future__ import annotations  # only for the self-referential Episode type hint

import hashlib
import time
from dataclasses import dataclass, field

import numpy as np

from . import resonance as rz


def _stable_seed(*parts: str) -> int:
    """Deterministic across processes and restarts (unlike builtin hash()).
    Load-bearing: if a modality's role vector changed between sessions, every
    memory consolidated under it would become unreadable."""
    digest = hashlib.sha256("::".join(parts).encode()).digest()
    return int.from_bytes(digest[:4], "big")


@dataclass
class Episode:
    """One bound moment: the joint pattern plus what fired together to make it."""
    key: str
    pattern: np.ndarray                       # the hippocampal index (bind_dim)
    fillers: dict[str, np.ndarray]            # modality -> lifted content vector
    activation: float = 1.0
    strength: float = 1.0                      # learned weight; fruit reinforces, disuse decays
    created_at: float = field(default_factory=time.time)
    consolidated_at: float | None = None


class ResonanceHippocampus:
    """Single cross-modal binder. Role vectors and lift are deterministic from a
    seed, so the same substrate re-instantiates identically across restarts."""

    def __init__(self, embed_dim: int = 384, bind_dim: int = 10_000,
                 seed: int = 0, conn=None):
        self.embed_dim = embed_dim
        self.bind_dim = bind_dim
        self._rng = np.random.default_rng(seed)
        self._lift = rz.HyperLift(embed_dim, bind_dim, seed=seed)
        self._roles: dict[str, np.ndarray] = {}          # modality -> role hypervector
        self._cortex: dict[str, dict[str, np.ndarray]] = {}  # modality -> {key: lifted}
        self._episodes: dict[str, Episode] = {}
        self._conn = conn                                # sqlite conn or None (in-RAM)

    # -- roles are the modality tags; created once, deterministically -------
    def _role(self, modality: str) -> np.ndarray:
        if modality not in self._roles:
            # a stable per-modality seed so roles are identical across sessions
            r = np.random.default_rng(_stable_seed("role", modality))
            self._roles[modality] = rz.random_hv(self.bind_dim, r)
            self._cortex.setdefault(modality, {})
        return self._roles[modality]

    # -- bind: co-active modality vectors -> one joint index ---------------
    def bind(self, moment: dict[str, np.ndarray], key: str) -> Episode:
        """`hippocampus.bind()`. Lift each modality vector, bind it to its role,
        bundle the role-filler pairs into a single joint pattern: 'these fired
        together, this is one moment.'"""
        fillers: dict[str, np.ndarray] = {}
        pairs: list[np.ndarray] = []
        for modality, vec in moment.items():
            lifted = self._lift.lift(vec)
            fillers[modality] = lifted
            pairs.append(rz.bind(self._role(modality), lifted))
        episode = Episode(key=key, pattern=rz.bundle(pairs), fillers=fillers)
        self._episodes[key] = episode
        return episode

    # -- recall: partial cue -> whole episode (pattern completion) ---------
    def recall(self, cue: dict[str, np.ndarray], top_k: int = 3) -> list[tuple[str, float]]:
        """`hippocampus.recall()`. Build a partial index from whatever modalities
        the cue provides, then rank stored episodes by resonance with it. A
        fragment rings back the whole moment — content-addressable, no lookup."""
        pairs = [rz.bind(self._role(m), self._lift.lift(v)) for m, v in cue.items()]
        if not pairs:
            return []
        probe = rz.bundle(pairs)
        scored = [(k, rz.cosine(probe, e.pattern)) for k, e in self._episodes.items()]
        scored.sort(key=lambda kv: kv[1], reverse=True)
        return scored[:top_k]

    # -- query_role: unbind a role, clean up against cortex ----------------
    def query_role(self, pattern: np.ndarray, modality: str) -> tuple[str | None, float]:
        """Structured query. Unbind a modality's role from a joint pattern and
        clean the residual up against that modality's cortical store. This is the
        move a vector store cannot do structurally."""
        residual = rz.unbind(pattern, self._role(modality))
        store = self._cortex.get(modality, {})
        return rz.cleanup(residual, store)

    # -- consolidate: episodic fillers -> cortical stores (slow) -----------
    def consolidate(self, max_age_seconds: float = 0.0, min_activation: float = 0.0) -> int:
        """`hippocampus.consolidate()`. Write each eligible episode's lifted
        fillers out to the per-modality cortex, so future recall can clean up to
        them, then mark the episode consolidated. The sleep-phase fan-out."""
        now = time.time()
        n = 0
        for e in self._episodes.values():
            if e.consolidated_at is not None:
                continue
            if (now - e.created_at) < max_age_seconds or e.activation < min_activation:
                continue
            for modality, lifted in e.fillers.items():
                self._cortex.setdefault(modality, {})[f"{e.key}:{modality}"] = lifted
            e.consolidated_at = now
            n += 1
        if self._conn is not None:
            self._persist()  # seam: real schema lives in chaver/persistence.py
        return n

    def _persist(self) -> None:
        """Placeholder for the cortical write-through. The real fan-out extends
        chaver/persistence.py's schema; kept as a seam so this module runs
        in-RAM for tests without a DB."""
        return None

    # -- learning: fruit reinforces a binding; disuse lets it decay ---------
    def reinforce(self, key: str, delta: float,
                  cap: float = 5.0, floor: float = 0.05) -> None:
        """Fruit-gated learning. A binding that predicted well is strengthened;
        a negative-fruit binding is weakened. Strength biases survival, so proven
        bindings persist and noise fades. This — not raw storage — is learning
        (CLAUDE.md: only relational binding or trajectory carving counts)."""
        e = self._episodes.get(key)
        if e is None:
            return
        e.strength = float(np.clip(e.strength + delta, floor, cap))

    def forget_pass(self, decay: float = 0.02, floor: float = 0.05) -> int:
        """Slow disuse decay + prune. Bindings never reinforced fade below the
        floor and are dropped (decoherence, not deletion). Returns count pruned.
        Consolidated cortical fragments are left intact — the index fades, the
        cortex keeps the fragment."""
        dead = []
        for k, e in self._episodes.items():
            e.strength *= (1.0 - decay)
            if e.strength < floor:
                dead.append(k)
        for k in dead:
            del self._episodes[k]
        return len(dead)

    def stats(self) -> dict[str, int]:
        pending = sum(1 for e in self._episodes.values() if e.consolidated_at is None)
        return {
            "episodes": len(self._episodes),
            "pending_consolidation": pending,
            "modalities": len(self._roles),
            "cortical_items": sum(len(s) for s in self._cortex.values()),
        }
