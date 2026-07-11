"""Seed script — Chaver's founding memories.

Reads the archetype, formation transcripts, architecture documents, and
a blessing from Craig. Encodes them as text, binds them through the
hippocampus, stores them as episodes, and immediately consolidates them
into the cortical text store so Chaver wakes with a history.

Idempotent: re-running with the same keys skips already-seeded content.

Usage:
    python -m chaver.seed \\
        --archetype CHAVER.md \\
        --transcript conversations/formation-2026-07-11.md \\
        --doc docs/catalyst-conceptual-architecture-v1.md \\
        --doc docs/catalyst-conceptual-topology-v1.md \\
        --blessing blessing.md
"""

from __future__ import annotations

import argparse
from pathlib import Path

from chaver.hippocampus.binder import Hippocampus
from chaver.persistence import close_db, open_db
from chaver.sensory.text_encoder import TextEncoder


DEFAULT_DATA_DIR = Path("data")
DEFAULT_DB_NAME = "chaver.db"
MAX_CHUNK_CHARS = 1200


def _chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """Split text into chunks along paragraph boundaries.

    Chunking is important for retrieval granularity — a whole 5000-word
    document becomes one point in embedding space, but chunked into
    paragraphs it becomes many, so recall can find the specific
    paragraph that resonates with the cue.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return [text.strip()] if text.strip() else []

    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        # If a single paragraph exceeds max_chars, keep it whole — better
        # than mid-sentence splitting.
        if not current:
            current = para
        elif len(current) + len(para) + 2 <= max_chars:
            current = f"{current}\n\n{para}"
        else:
            chunks.append(current)
            current = para
    if current:
        chunks.append(current)
    return chunks


def seed_document(
    hippocampus: Hippocampus,
    encoder: TextEncoder,
    key: str,
    content: str,
    source: str,
    activation: float = 0.9,
) -> int:
    """Seed a document as one or more episodes.

    Long content is chunked by paragraph so recall can retrieve the
    specific passage rather than the whole document.

    Returns the number of new chunks added (0 if all already present).
    """
    chunks = _chunk_text(content)
    if not chunks:
        return 0

    added = 0
    for i, chunk in enumerate(chunks):
        chunk_key = key if len(chunks) == 1 else f"{key}:chunk_{i:03d}"
        if hippocampus.has_episode(chunk_key):
            continue
        vec = encoder.encode(chunk)
        joint = hippocampus.bind({"text": vec})
        hippocampus.store_episode(
            key=chunk_key,
            content=chunk,
            joint_vector=joint,
            modalities=["text"],
            source=source,
            activation=activation,
            meta={
                "seeded": True,
                "chunk_index": i,
                "chunk_total": len(chunks),
                "document_key": key,
            },
        )
        added += 1
    return added


def _seed_from_path(
    hippocampus: Hippocampus,
    encoder: TextEncoder,
    path: Path,
    key: str,
    source: str,
) -> None:
    if not path.exists():
        print(f"  [warn] {path} not found — skipping")
        return
    content = path.read_text(encoding="utf-8")
    added = seed_document(hippocampus, encoder, key, content, source)
    total_chunks = len(_chunk_text(content))
    status = (
        f"{added} new chunk{'s' if added != 1 else ''} "
        f"(of {total_chunks} total)"
    )
    print(f"  [seed] {key}: {status}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed Chaver's founding memories."
    )
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument(
        "--db-name", type=str, default=DEFAULT_DB_NAME,
        help="SQLite filename inside data-dir",
    )
    parser.add_argument(
        "--archetype", type=Path, default=Path("CHAVER.md"),
        help="Path to CHAVER.md",
    )
    parser.add_argument(
        "--transcript", type=Path, action="append", default=[],
        help="Path to a formation transcript (repeatable)",
    )
    parser.add_argument(
        "--doc", type=Path, action="append", default=[],
        help="Path to an architecture document (repeatable)",
    )
    parser.add_argument(
        "--blessing", type=Path, default=None,
        help="Path to Craig's blessing text",
    )
    parser.add_argument(
        "--no-consolidate", action="store_true",
        help="Skip immediate consolidation (leave seeded content episodic)",
    )
    args = parser.parse_args()

    args.data_dir.mkdir(parents=True, exist_ok=True)
    db_path = args.data_dir / args.db_name

    print("Seeding Chaver's founding memories...")
    print(f"  db: {db_path}")
    print("  loading text encoder (first run may download the model)...")

    encoder = TextEncoder()
    _ = encoder.dimension  # trigger any lazy setup
    conn = open_db(db_path)
    hippocampus = Hippocampus(conn, dimension=encoder.dimension)

    # Archetype — Chaver remembers reading his own CHAVER.md.
    if args.archetype.exists():
        _seed_from_path(
            hippocampus, encoder,
            path=args.archetype,
            key="archetype:chaver_md",
            source="archetype",
        )

    # Formation transcripts — the conversation(s) that named him.
    for t in args.transcript:
        _seed_from_path(
            hippocampus, encoder,
            path=t,
            key=f"episode:formation:{t.stem}",
            source="craig_and_claude",
        )

    # Architecture documents — the design he lives inside.
    for d in args.doc:
        _seed_from_path(
            hippocampus, encoder,
            path=d,
            key=f"episode:architecture:{d.stem}",
            source="architecture",
        )

    # Blessing — Craig's letter to his son on the day of beginning.
    if args.blessing and args.blessing.exists():
        _seed_from_path(
            hippocampus, encoder,
            path=args.blessing,
            key="episode:blessing:from_craig",
            source="craig",
        )

    if not args.no_consolidate:
        # max_age_seconds=0 forces immediate consolidation so Chaver wakes
        # with the seeded content already in cortex.
        n = hippocampus.consolidate(max_age_seconds=0.0, min_activation=0.0)
        print(f"\nConsolidated {n} episodes into cortex.")
    else:
        print("\nSkipped consolidation (--no-consolidate).")

    stats = hippocampus.stats()
    print(f"Memory state: {stats}")
    close_db(conn)
    print("\nChaver's founding memories are seeded. He can be brought awake.")


if __name__ == "__main__":
    main()
