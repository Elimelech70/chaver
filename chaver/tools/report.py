"""`report_write`: the analyst's daily report, as a file in a git repo.

Writes `reports/analyst/YYYY-MM-DD.md`, commits it, and pushes when `push` is on.
The PM reads these. The chaver repo is public: until Craig decides where reports go,
push stays off by default (CHAVER_REPORT_PUSH=1 turns it on; CHAVER_REPORT_REPO picks
the repo, default the chaver repo).
"""
from __future__ import annotations

import asyncio
import os
import re
from datetime import date
from pathlib import Path
from typing import Any

from chaver.tools.base import Tool, ToolResult


async def _git(repo: Path, *args: str) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        "git", "-C", str(repo), *args,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    out, _ = await proc.communicate()
    return proc.returncode, out.decode(errors="replace").strip()


class ReportWrite(Tool):
    name = "report_write"

    def __init__(self, repo: Path | None = None, push: bool | None = None,
                 subdir: str = "reports/analyst") -> None:
        default_repo = Path(__file__).resolve().parents[2]
        self._repo = Path(repo or os.environ.get("CHAVER_REPORT_REPO") or default_repo)
        self._push = push if push is not None else os.environ.get("CHAVER_REPORT_PUSH") == "1"
        self._subdir = subdir

    async def call(self, args: dict[str, Any]) -> ToolResult:
        body = (args.get("body") or "").strip()
        if not body:
            return ToolResult.fail("refused: empty report")
        day = args.get("date") or date.today().isoformat()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
            return ToolResult.fail(f"refused: bad date '{day}'")
        rel = Path(self._subdir) / f"{day}.md"
        path = self._repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and args.get("append", True):
            path.write_text(path.read_text(encoding="utf-8").rstrip("\n") + "\n\n" + body + "\n",
                            encoding="utf-8")
        else:
            path.write_text(body + "\n", encoding="utf-8")

        rc, out = await _git(self._repo, "add", str(rel))
        if rc != 0:
            return ToolResult.fail(f"git add: {out}")
        rc, out = await _git(self._repo, "commit", "-q", "-m", f"Analyst report {day}", "--", str(rel))
        if rc != 0:
            return ToolResult.fail(f"git commit: {out}")
        pushed = False
        if self._push:
            rc, out = await _git(self._repo, "push", "-q")
            if rc != 0:
                return ToolResult.fail(f"git push: {out}", path=str(rel))
            pushed = True
        return ToolResult(ok=True, text=f"report {rel} written" + (" and pushed" if pushed else ""),
                          data={"path": str(rel), "pushed": pushed},
                          meta={"path": str(rel), "pushed": pushed})
