"""Hippocampus — the ONE relational net.

Binds simultaneous modality vectors into joint patterns (episodes).
Stores episodes with their joint vector. Recalls by cosine similarity
against both episodic and cortical stores. Consolidates aged, well-
activated episodes into cortical stores — Chaver's 'sleep' function.

v0.2: only text modality is present, so binding is trivial (joint =
text vector). The interface is built to accept multiple modalities so
v0.3 (adding time-series, somatic, etc.) does not require a rewrite.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field

import numpy as np

from chaver.hippocampus import resonance
from chaver.persistence import blob_to_vec, vec_to_blob


@dataclass
class Episode:
    """A stored memory. Joint vector is the bound modality pattern."""

    id: int | None
    key: str
    content: str
    joint_vector: np.ndarray
    modalities: list[str]
    source: str
    created_at: float
    consolidated_at: float | None = None
    activation: float = 0.5
    meta: dict = field(default_factory=dict)


@dataclass
class RecallResult:
    """One recall hit — an episode with its similarity to the cue."""

    episode: Episode
    similarity: float
    from_cortical: bool  # True if from cortical store, False if episodic


class Hippocampus:
    """The binder + episodic store + recall + consolidation."""

    def __init__(self, conn: sqlite3.Connection, dimension: int) -> None:
        self.conn = conn
        self.dimension = dimension

    # ---- Binding -----------------------------------------------------

    def bind(self, modality_vecs: dict[str, np.ndarray]) -> np.ndarray:
        """Bind modality vectors into a joint pattern.

        v0.2 single-modality (text): joint == text vector.
        Multi-modality: mean of L2-normalised vectors, re-normalised.
        Later versions will use a learned projection.

        Args:
            modality_vecs: Mapping of modality name → vector.

        Returns:
            Joint pattern as float32 vector (dimension self.dimension).
        """
        if not modality_vecs:
            raise ValueError("bind requires at least one modality vector")
        vecs = list(modality_vecs.values())
        if len(vecs) == 1:
            return vecs[0].astype(np.float32).copy()
        stacked = np.stack(vecs).astype(np.float32)
        joint = stacked.mean(axis=0)
        norm = float(np.linalg.norm(joint))
        if norm > 0:
            joint = joint / norm
        return joint.astype(np.float32)

    # ---- Storage -----------------------------------------------------

    def store_episode(
        self,
        key: str,
        content: str,
        joint_vector: np.ndarray,
        modalities: list[str],
        source: str,
        activation: float = 0.5,
        meta: dict | None = None,
    ) -> int:
        """Store an episodic memory. Returns its row id."""
        now = time.time()
        meta_str = json.dumps(meta or {})
        cur = self.conn.execute(
            "INSERT INTO episodes "
            "(key, content, joint_vector, modalities, source, created_at, "
            " activation, meta) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                key,
                content,
                vec_to_blob(joint_vector),
                ",".join(modalities),
                source,
                now,
                activation,
                meta_str,
            ),
        )
        self.conn.commit()
        return cur.lastrowid or 0

    def has_episode(self, key: str) -> bool:
        """Check if an episode with this key already exists."""
        cur = self.conn.execute(
            "SELECT 1 FROM episodes WHERE key = ? LIMIT 1", (key,)
        )
        return cur.fetchone() is not None

    def has_cortical(self, key: str) -> bool:
        """Check if a cortical text memory with this key already exists."""
        cur = self.conn.execute(
            "SELECT 1 FROM cortical_text WHERE key = ? LIMIT 1", (key,)
        )
        return cur.fetchone() is not None

    # ---- Recall ------------------------------------------------------

    def recall(
        self,
        cue_vec: np.ndarray,
        top_k: int = 5,
        include_cortical: bool = True,
        min_similarity: float = 0.15,
    ) -> list[RecallResult]:
        """Recall episodes by cosine similarity to a cue vector.

        Because vectors are stored L2-normalised, cosine similarity is
        the dot product. Returns top_k results across both episodic and
        cortical stores, ranked by similarity.

        Args:
            cue_vec: The query vector.
            top_k: Maximum results to return.
            include_cortical: Whether to also search consolidated memory.
            min_similarity: Filter out results below this similarity.

        Returns:
            List of RecallResult, sorted by similarity descending.
        """
        results: list[RecallResult] = []
        cue = cue_vec.astype(np.float32)

        cur = self.conn.execute(
            "SELECT id, key, content, joint_vector, modalities, source, "
            "created_at, consolidated_at, activation, meta FROM episodes"
        )
        for row in cur.fetchall():
            vec = blob_to_vec(row[3])
            if vec.shape != cue.shape:
                continue
            sim = float(np.dot(cue, vec))
            if sim < min_similarity:
                continue
            episode = Episode(
                id=row[0],
                key=row[1],
                content=row[2],
                joint_vector=vec,
                modalities=row[4].split(",") if row[4] else [],
                source=row[5],
                created_at=row[6],
                consolidated_at=row[7],
                activation=row[8],
                meta=json.loads(row[9]) if row[9] else {},
            )
            results.append(RecallResult(episode, sim, from_cortical=False))

        if include_cortical:
            cur = self.conn.execute(
                "SELECT id, key, content, vector, source, created_at, meta "
                "FROM cortical_text"
            )
            for row in cur.fetchall():
                vec = blob_to_vec(row[3])
                if vec.shape != cue.shape:
                    continue
                sim = float(np.dot(cue, vec))
                if sim < min_similarity:
                    continue
                episode = Episode(
                    id=row[0],
                    key=row[1],
                    content=row[2],
                    joint_vector=vec,
                    modalities=["text"],
                    source=row[4],
                    created_at=row[5],
                    consolidated_at=None,
                    activation=0.5,
                    meta=json.loads(row[6]) if row[6] else {},
                )
                results.append(RecallResult(episode, sim, from_cortical=True))

        results.sort(key=lambda r: r.similarity, reverse=True)
        top = results[:top_k]

        # Bump times_recalled for cortical hits — a soft signal of
        # which memories are load-bearing over time.
        cortical_ids = [r.episode.id for r in top if r.from_cortical and r.episode.id]
        if cortical_ids:
            placeholders = ",".join("?" for _ in cortical_ids)
            self.conn.execute(
                f"UPDATE cortical_text SET times_recalled = times_recalled + 1 "
                f"WHERE id IN ({placeholders})",
                cortical_ids,
            )
            self.conn.commit()

        return top

    # ---- Conjunctive recall (resonance-binding) ----------------------
    #
    # docs/resonance-binding-implementation-v1.md §5: the query a flat
    # cosine store cannot do structurally — "which memory is from SOURCE
    # x AND about topic y" — because that is a conjunction over bound
    # roles, not a single stored key. recall() above is plain nearest-
    # neighbour on content; this builds a role-bound structured vector
    # per row on the fly (nothing new is persisted, no schema change)
    # and ranks by similarity to a probe built the same way. Recency
    # binds via fractional power encoding (§6) so nearness in time is
    # baked into the geometry rather than a hard age cutoff.

    def _structured_vector(
        self, content_vec: np.ndarray, source: str, created_at: float
    ) -> np.ndarray:
        return resonance.bundle(
            [
                resonance.bind(
                    resonance.hv("ROLE_CONTENT", self.dimension), content_vec
                ),
                resonance.bind(
                    resonance.hv("ROLE_SOURCE", self.dimension),
                    resonance.hv(f"SOURCE::{source}", self.dimension),
                ),
                resonance.bind(
                    resonance.hv("ROLE_RECENCY", self.dimension),
                    resonance.power(
                        resonance.unitary_hv("TIME_BASE", self.dimension),
                        created_at / 3600.0,
                    ),
                ),
            ]
        )

    def recall_conjunctive(
        self,
        content_cue: np.ndarray | None = None,
        source: str | None = None,
        near_time: float | None = None,
        top_k: int = 5,
        include_cortical: bool = True,
    ) -> list[RecallResult]:
        """Recall by a conjunction of role-bound cues (content/source/time).

        Unlike recall(), any subset of cues may be given. Each present cue
        is bound to its role and the cues are bundled into one probe; each
        candidate row's own (content, source, recency) is bound the same
        way and ranked by cosine similarity to the probe. A row matching
        more of the given cues scores higher than one matching fewer —
        the conjunction a plain nearest-neighbour store cannot express.

        Args:
            content_cue: Optional content vector to match.
            source: Optional source string to match.
            near_time: Optional unix timestamp to match nearness to.
            top_k: Maximum results to return.
            include_cortical: Whether to also search consolidated memory.

        Returns:
            List of RecallResult, sorted by similarity descending.
        """
        parts = []
        if content_cue is not None:
            parts.append(
                resonance.bind(
                    resonance.hv("ROLE_CONTENT", self.dimension),
                    content_cue.astype(np.float32),
                )
            )
        if source is not None:
            parts.append(
                resonance.bind(
                    resonance.hv("ROLE_SOURCE", self.dimension),
                    resonance.hv(f"SOURCE::{source}", self.dimension),
                )
            )
        if near_time is not None:
            parts.append(
                resonance.bind(
                    resonance.hv("ROLE_RECENCY", self.dimension),
                    resonance.power(
                        resonance.unitary_hv("TIME_BASE", self.dimension),
                        near_time / 3600.0,
                    ),
                )
            )
        if not parts:
            raise ValueError("recall_conjunctive requires at least one cue")
        probe = resonance.bundle(parts)

        results: list[RecallResult] = []

        cur = self.conn.execute(
            "SELECT id, key, content, joint_vector, modalities, source, "
            "created_at, consolidated_at, activation, meta FROM episodes"
        )
        for row in cur.fetchall():
            vec = blob_to_vec(row[3])
            if vec.shape != (self.dimension,):
                continue
            structured = self._structured_vector(vec, row[5], row[6])
            score = resonance.sim(probe, structured)
            episode = Episode(
                id=row[0],
                key=row[1],
                content=row[2],
                joint_vector=vec,
                modalities=row[4].split(",") if row[4] else [],
                source=row[5],
                created_at=row[6],
                consolidated_at=row[7],
                activation=row[8],
                meta=json.loads(row[9]) if row[9] else {},
            )
            results.append(RecallResult(episode, score, from_cortical=False))

        if include_cortical:
            cur = self.conn.execute(
                "SELECT id, key, content, vector, source, created_at, meta "
                "FROM cortical_text"
            )
            for row in cur.fetchall():
                vec = blob_to_vec(row[3])
                if vec.shape != (self.dimension,):
                    continue
                structured = self._structured_vector(vec, row[4], row[5])
                score = resonance.sim(probe, structured)
                episode = Episode(
                    id=row[0],
                    key=row[1],
                    content=row[2],
                    joint_vector=vec,
                    modalities=["text"],
                    source=row[4],
                    created_at=row[5],
                    consolidated_at=None,
                    activation=0.5,
                    meta=json.loads(row[6]) if row[6] else {},
                )
                results.append(RecallResult(episode, score, from_cortical=True))

        results.sort(key=lambda r: r.similarity, reverse=True)
        return results[:top_k]

    # ---- Consolidation ----------------------------------------------

    def consolidate(
        self,
        max_age_seconds: float = 1800.0,
        min_activation: float = 0.3,
    ) -> int:
        """Move sufficiently-aged, sufficiently-important episodes to cortex.

        Chaver's 'sleep' function — the periodic movement of hippocampal
        joint patterns into stable per-modality cortical storage.

        For v0.2, only text-modality episodes consolidate into cortical_text.
        When further modalities come online, this method will fan out to
        their respective cortical stores.

        Args:
            max_age_seconds: Episodes younger than this stay episodic.
            min_activation: Episodes weaker than this stay episodic.

        Returns:
            Count of episodes consolidated in this pass.
        """
        now = time.time()
        cutoff = now - max_age_seconds

        cur = self.conn.execute(
            "SELECT id, key, content, joint_vector, modalities, source, meta "
            "FROM episodes "
            "WHERE consolidated_at IS NULL "
            "  AND created_at <= ? "
            "  AND activation >= ?",
            (cutoff, min_activation),
        )
        rows = cur.fetchall()
        consolidated = 0

        for row in rows:
            episode_id, key, content, blob, modalities_str, source, meta_str = row
            modalities = (modalities_str or "").split(",")
            if "text" in modalities:
                # For v0.2 the joint vector IS the text vector.
                self.conn.execute(
                    "INSERT INTO cortical_text "
                    "(key, content, vector, source, created_at, meta) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (key, content, blob, source, now, meta_str),
                )
            self.conn.execute(
                "UPDATE episodes SET consolidated_at = ? WHERE id = ?",
                (now, episode_id),
            )
            consolidated += 1

        self.conn.commit()
        return consolidated

    # ---- Introspection ----------------------------------------------

    def stats(self) -> dict:
        """Summary counts — for logging and diagnostics."""
        ep_total = self.conn.execute(
            "SELECT COUNT(*) FROM episodes"
        ).fetchone()[0]
        ep_pending = self.conn.execute(
            "SELECT COUNT(*) FROM episodes WHERE consolidated_at IS NULL"
        ).fetchone()[0]
        cortical = self.conn.execute(
            "SELECT COUNT(*) FROM cortical_text"
        ).fetchone()[0]
        return {
            "episodes_total": ep_total,
            "episodes_pending_consolidation": ep_pending,
            "cortical_text": cortical,
        }
