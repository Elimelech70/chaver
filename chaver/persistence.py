"""Persistence — sqlite as Chaver's long-term substrate.

Two tables: episodes (hippocampal) and cortical_text (consolidated text
memories). Vectors stored as float32 numpy blobs.

Cortex is per-modality in the design; v0.2 has only cortical_text. Later
versions add cortical_visual, cortical_timeseries, cortical_somatic, etc.
Hippocampus is the single binder across all of them.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np


SCHEMA = """
CREATE TABLE IF NOT EXISTS episodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL,
    content TEXT NOT NULL,
    joint_vector BLOB NOT NULL,
    modalities TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at REAL NOT NULL,
    consolidated_at REAL,
    activation REAL NOT NULL DEFAULT 0.5,
    meta TEXT
);

CREATE INDEX IF NOT EXISTS idx_episodes_key ON episodes(key);
CREATE INDEX IF NOT EXISTS idx_episodes_consolidated ON episodes(consolidated_at);
CREATE INDEX IF NOT EXISTS idx_episodes_created ON episodes(created_at);

CREATE TABLE IF NOT EXISTS cortical_text (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL,
    content TEXT NOT NULL,
    vector BLOB NOT NULL,
    source TEXT NOT NULL,
    created_at REAL NOT NULL,
    times_recalled INTEGER NOT NULL DEFAULT 0,
    meta TEXT
);

CREATE INDEX IF NOT EXISTS idx_cortical_text_key ON cortical_text(key);
"""


def vec_to_blob(vec: np.ndarray) -> bytes:
    """Serialise a float32 vector to bytes for SQLite storage."""
    return vec.astype(np.float32).tobytes()


def blob_to_vec(blob: bytes) -> np.ndarray:
    """Deserialise a float32 vector from bytes."""
    return np.frombuffer(blob, dtype=np.float32)


def open_db(path: Path) -> sqlite3.Connection:
    """Open (creating if needed) Chaver's memory database.

    Args:
        path: Path to the SQLite file. Parent directory is created if
            it does not exist.

    Returns:
        A configured sqlite3.Connection with schema applied.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def close_db(conn: sqlite3.Connection) -> None:
    """Close the memory database cleanly."""
    conn.commit()
    conn.close()
