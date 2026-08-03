"""Resonance-binding — the VSA algebra under hippocampus.bind/recall.

Implements docs/resonance-binding-implementation-v1.md as runtime code:
BIND (circular convolution), UNBIND (circular correlation), BUNDLE
(superposition), and cleanup (cortex-as-codebook readout), plus fractional
power encoding (FPE) for continuous quantities like recency.

Deliberately run at Chaver's real embedding width (384, TEXT_EMBEDDING_DIM)
rather than the doc's demonstration width of 10,000. That keeps one vector
space and one blob format across the codebase — no second embedding
pipeline, no schema change. The tradeoff, stated plainly per the doc's own
discipline: near-orthogonality is weaker at this width (mean |cosine| among
random vectors scales roughly as 1/sqrt(dim), so ~0.05 here vs ~0.008 at
10,000 in the doc). Chaver's codebooks (sources, role fillers) are small —
tens of items, not thousands — so cleanup still resolves cleanly. See
binding_demo.py at the repo root for the doc's own numbers, reproduced
verbatim at D=10,000.
"""

from __future__ import annotations

import hashlib

import numpy as np


def _seed_from_name(name: str) -> int:
    """Deterministic seed so a role/filler vector is stable across restarts."""
    digest = hashlib.sha256(name.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def hv(name: str, dim: int) -> np.ndarray:
    """A deterministic random direction in dim-D space, keyed by name.

    Same name always yields the same vector (no persistence needed) —
    this is the role/filler codebook: ROLE_SOURCE, ROLE_RECENCY, a given
    source string, etc. are all just names handed to this function.
    """
    rng = np.random.default_rng(_seed_from_name(name))
    v = rng.standard_normal(dim).astype(np.float32)
    return v / np.linalg.norm(v)


def unitary_hv(name: str, dim: int) -> np.ndarray:
    """A deterministic unit-magnitude-spectrum vector, for use as an FPE base.

    Unlike hv(), every frequency component has magnitude 1 — this is what
    makes power() a smooth, phase-safe dial rather than a decaying one.
    """
    rng = np.random.default_rng(_seed_from_name(name))
    half = dim // 2 + 1
    phases = rng.uniform(-np.pi, np.pi, half)
    spec = np.exp(1j * phases)
    spec[0] = 1.0
    if dim % 2 == 0:
        spec[-1] = 1.0
    v = np.fft.irfft(spec, n=dim).astype(np.float32)
    return v / np.linalg.norm(v)


def bind(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """BIND — circular convolution. Glues two vectors into one resembling neither."""
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


def sim(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity — the only readout."""
    denom = np.linalg.norm(a) * np.linalg.norm(b) + 1e-12
    return float(np.dot(a, b) / denom)


def power(base: np.ndarray, exponent: float) -> np.ndarray:
    """Fractional power encoding — base ** real exponent, phase-safe.

    Turns a discrete symbol (base) into a continuous, addressable dial:
    nearby exponents give nearby vectors (see docs §6). Used here so
    recency binds as a smooth quantity rather than a hard age cutoff.
    """
    spec = np.fft.rfft(base)
    spec = np.exp(exponent * np.log(spec + 0j))
    return np.fft.irfft(spec, n=len(base)).astype(np.float32)


def cleanup(
    noisy: np.ndarray, codebook: dict[str, np.ndarray]
) -> tuple[str | None, float]:
    """Cortex-as-codebook readout: which known item does noisy resemble most?"""
    best, best_s = None, -1.0
    for name, vec in codebook.items():
        s = sim(noisy, vec)
        if s > best_s:
            best, best_s = name, s
    return best, best_s


# ---- Compatibility + hyperdimensional lift ---------------------------
#
# Folded in from the memory-and-learning core's reconstructed resonance
# module when the two environments were merged. `cosine` is the name the
# corpus and the learning proof use for `sim` (identical readout), kept as
# an alias so either name resolves. `random_hv` and `HyperLift` belong to
# the isolated 10,000-D proof path and are NOT used by the persisted 384-D
# runtime (one vector space, one blob format — see the module docstring);
# they live here so the single resonance module is complete for the day a
# modality genuinely needs hyperdimensional width, rather than being lost
# with the retired learning_core.

cosine = sim  # corpus/proof name for the cosine readout


def random_hv(dim: int, rng: np.random.Generator) -> np.ndarray:
    """A random direction in dim-D space, drawn from the caller's rng.

    Unlike hv() (name-keyed, content-addressed), this takes an explicit
    numpy Generator — used where a locally-seeded per-role vector is wanted.
    """
    v = rng.standard_normal(dim).astype(np.float32)
    return v / np.linalg.norm(v)


class HyperLift:
    """A frozen, seeded random projection from an embedder's native width
    (embed_dim, e.g. 384) up into a shared hyperdimensional binding space
    (bind_dim, e.g. 10,000).

    An unlearned Gaussian projection scaled by 1/sqrt(embed_dim) (a
    Johnson-Lindenstrauss construction) that approximately preserves
    pairwise distances and near-orthogonality once lifted. Seeded and never
    updated, so the same embed_dim vector lifts to the same bind_dim vector
    across restarts with no training and no persistence of the matrix.

    Not used by the current 384-D persisted path; retained for the point at
    which a modality needs cleaner high-dimensional unbinding than 384-D
    gives (see resonance module docstring on the near-orthogonality
    tradeoff at 384-D).
    """

    def __init__(self, embed_dim: int, bind_dim: int, seed: int = 0) -> None:
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
