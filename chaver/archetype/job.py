"""Job — what Chaver is doing, held separately from who he is.

`CHAVER.md` is his identity (DNA). `JOB.md` is his job: role, goal, objectives with
KPIs, processes, guardrails, autonomy, edges and neighbours. A job is switched on with
`CHAVER_JOB=<path>` (normally `JOB.md`); unset, Chaver behaves exactly as before.

Like CHAVER.md, JOB.md is runtime, not documentation: its full text is kept verbatim and
passed to the language faculty after CHAVER.md on every call. It is never summarised,
truncated, or seeded as a memory to be paraphrased.

Structured fields are parsed from these second-level headings (any order; others ignored):

    ## Role                      free text
    ## Goal                      free text (becomes the executive's goal)
    ## Objectives and KPIs       bullet list
    ## Function and processes    bullet list (become the strategy's steps)
    ## Guardrails                bullet list
    ## Autonomy                  free text
    ## Your Edges                "Own domain: ..." line, then bullets (own edges)
    ## Neighbours                bullets: "- **Name** — domain. Signals: a, b, c"
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from chaver.archetype.model import Neighbour

JOB_ENV = "CHAVER_JOB"


@dataclass
class Job:
    """Chaver's job, loaded from JOB.md. `text` is the full file, verbatim."""

    text: str
    path: Path
    role: str = ""
    goal: str = ""
    objectives: list[str] = field(default_factory=list)
    processes: list[str] = field(default_factory=list)
    guardrails: list[str] = field(default_factory=list)
    autonomy: str = ""
    own_domain: str = ""
    own_edges: list[str] = field(default_factory=list)
    neighbours: list[Neighbour] = field(default_factory=list)


def _sections(text: str) -> dict[str, str]:
    """Split markdown into {lower-cased '## heading': body}."""
    out: dict[str, str] = {}
    current: str | None = None
    buf: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            if current is not None:
                out[current] = "\n".join(buf).strip()
            current = m.group(1).strip().lower()
            buf = []
        elif current is not None:
            buf.append(line)
    if current is not None:
        out[current] = "\n".join(buf).strip()
    return out


def _bullets(body: str) -> list[str]:
    """Top-level bullet items, continuation lines joined."""
    items: list[str] = []
    for line in body.splitlines():
        m = re.match(r"^[-*]\s+(.*)$", line)
        if m:
            items.append(m.group(1).strip())
        elif items and line.startswith((" ", "\t")) and line.strip():
            items[-1] += " " + line.strip()
    return items


def _prose(body: str) -> str:
    """Body text without bullets, blank-line paragraphs joined by a space."""
    lines = [l.strip() for l in body.splitlines()
             if l.strip() and not re.match(r"^[-*]\s+", l) and l.strip() != "---"]
    return " ".join(lines)


_NEIGHBOUR = re.compile(
    r"^\*\*(?P<name>[^*]+)\*\*\s*[—–-]\s*(?P<domain>.*?)(?:\.\s*Signals?:\s*(?P<signals>.*))?$"
)


def _neighbours(body: str) -> list[Neighbour]:
    out: list[Neighbour] = []
    for item in _bullets(body):
        m = _NEIGHBOUR.match(item)
        if not m:
            continue
        signals = [s.strip().rstrip(".") for s in (m.group("signals") or "").split(",") if s.strip()]
        out.append(Neighbour(name=m.group("name").strip(),
                             domain=m.group("domain").strip().rstrip("."),
                             signals=signals))
    return out


def load_job(job_md_path: Path) -> Job:
    """Load JOB.md. The full text is kept byte-for-byte in `Job.text`."""
    if not job_md_path.exists():
        raise FileNotFoundError(
            f"JOB.md not found at {job_md_path} ({JOB_ENV} is set). "
            f"Unset {JOB_ENV} to run Chaver without a job."
        )
    text = job_md_path.read_text(encoding="utf-8")
    s = _sections(text)

    edges_body = s.get("your edges", "")
    own_domain = ""
    for line in edges_body.splitlines():
        m = re.match(r"^\s*Own domain:\s*(.+)$", line, re.IGNORECASE)
        if m:
            own_domain = m.group(1).strip()
            break

    return Job(
        text=text,
        path=job_md_path,
        role=_prose(s.get("role", "")),
        goal=_prose(s.get("goal", "")),
        objectives=_bullets(s.get("objectives and kpis", "")),
        processes=_bullets(s.get("function and processes", "")),
        guardrails=_bullets(s.get("guardrails", "")),
        autonomy=_prose(s.get("autonomy", "")),
        own_domain=own_domain,
        own_edges=_bullets(edges_body),
        neighbours=_neighbours(s.get("neighbours", "")),
    )


def job_path_from_env(base_dir: Path) -> Path | None:
    """Path named by CHAVER_JOB (relative to base_dir), or None when unset/empty."""
    value = os.environ.get(JOB_ENV, "").strip()
    if not value:
        return None
    p = Path(value)
    return p if p.is_absolute() else base_dir / p
