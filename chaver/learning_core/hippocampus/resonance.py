"""VSA substrate for the learning core — bind/unbind/bundle, cosine, cleanup,
and the HyperLift that resolves the dimensional mismatch CHAVER_BUILD_GUIDE.md
§3 describes.

NOT part of the delivered zip. The build guide's own file inventory (§2) lists
`hippocampus/resonance.py` as "tested" and describes its contents (§3: HyperLift,
a frozen seeded random projection) in enough detail to reconstruct the required
API — but the file itself was absent from Chaver Implementation.zip, and
binder.py / heartbeat.py both import names from it (`HyperLift`, `random_hv`,
`bind`, `unbind`, `bundle`, `cosine`, `cleanup`) that exist nowhere else in the
delivery. Written here to that exact contract so the acceptance test could run
at all. See docs/Implementation/INTEGRATION_REPORT.md.

Algebra is the same HRR (circular convolution / correlation) used in
chaver/hippocampus/resonance.py (the production module, docs/resonance-binding-
implementation-v1.md) — this is a separate module, not a re-export, because the
production module's `hv()` is name-keyed (content-addressed, no external rng)
while this one takes an explicit `rng`, matching how binder.py calls it
(`rz.random_hv(self.bind_dim, r)` with a locally-seeded generator per role).
"""

from __future__ import annotations

import numpy as np


def random_hv(dim: int, rng: np.random.Generator) -> np.ndarray:
    """A random direction in dim-D space, drawn from the caller's rng."""
    v = rng.standard_normal(dim).astype(np.float32)
    return v / np.linalg.norm(v)


def bind(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """BIND — circular convolution (HRR)."""
    return np.fft.irfft(np.fft.rfft(a) * np.fft.rfft(b), n=len(a)).astype(np.float32)


def unbind(c: np.ndarray, a: np.ndarray) -> np.ndarray:
    """UNBIND — circular correlation, the approximate inverse of bind(a, ·)."""
    return np.fft.irfft(
        np.fft.rfft(c) * np.conj(np.fft.rfft(a)), n=len(c)
    ).astype(np.float32)


def bundle(vecs: list[np.ndarray]) -> np.ndarray:
    """BUNDLE — superpose several vectors into one, L2-normalised."""
    s = np.sum(vecs, axis=0)
    norm = np.linalg.norm(s)
    if norm > 0:
        s = s / norm
    return s.astype(np.float32)


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    """The only readout."""
    denom = np.linalg.norm(a) * np.linalg.norm(b) + 1e-12
    return float(np.dot(a, b) / denom)


def cleanup(
    noisy: np.ndarray, codebook: dict[str, np.ndarray]
) -> tuple[str | None, float]:
    """Cortex-as-codebook readout: which known item does noisy resemble most?"""
    best, best_s = None, -1.0
    for name, vec in codebook.items():
        s = cosine(noisy, vec)
        if s > best_s:
            best, best_s = name, s
    return best, best_s


class HyperLift:
    """A frozen, seeded random projection from an embedder's native width
    (embed_dim, e.g. 384) up into the shared hyperdimensional binding space
    (bind_dim, default 10,000).

    Per CHAVER_BUILD_GUIDE.md §3: Chaver's small per-modality embedders stay
    small (CLAUDE.md principle 7 — many small embedders), but VSA binding
    needs hyperdimensional width for clean unbinding. This resolves that
    without training: an unlearned Gaussian projection, scaled by 1/sqrt(k)
    so a unit-norm input maps to an approximately unit-norm output (standard
    Johnson-Lindenstrauss construction — the projection approximately
    preserves pairwise distances/near-orthogonality between embed_dim
    vectors once lifted to bind_dim). Seeded and never updated, so the same
    embed_dim vector lifts to the same bind_dim vector every time, across
    restarts, with no training step and no persistence of the matrix itself.
    """

    def __init__(self, embed_dim: int, bind_dim: int, seed: int = 0):
        self.embed_dim = embed_dim
        self.bind_dim = bind_dim
        rng = np.random.default_rng(seed)
        self._matrix = (
            rng.standard_normal((bind_dim, embed_dim)).astype(np.float32)
            / np.sqrt(embed_dim)
        )

    def lift(self, vec: np.ndarray) -> np.ndarray:
        v = np.asarray(vec, dtype=np.float32)
        if v.shape != (self.embed_dim,):
            raise ValueError(
                f"HyperLift expected a {self.embed_dim}-dim vector, got {v.shape}"
            )
        lifted = self._matrix @ v
        norm = np.linalg.norm(lifted)
        if norm > 0:
            lifted = lifted / norm
        return lifted.astype(np.float32)
