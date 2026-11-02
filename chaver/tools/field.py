"""Tool results enter Chaver through the field, as web search results do:
encode → excite in working memory → store as an episode (source `tool:<name>`)."""
from __future__ import annotations

import time

from chaver.tools.base import ToolResult


def ingest(state, tool_name: str, result: ToolResult, strength: float = 0.6) -> bool:
    """Load one tool result into the field. Returns True if it entered working memory."""
    text = result.text if result.ok else (result.text or f"[tool error] {result.error}")
    if not text.strip():
        return False
    source = f"tool:{tool_name}"
    key = f"{source}:{int(time.time() * 1000)}"
    state.working_memory.excite(key=key, content=text, source=source,
                                strength=strength if result.ok else strength / 2,
                                metadata={"ok": result.ok, **result.meta})
    if state.hippocampus is not None and state.text_encoder is not None:
        try:
            vec = state.text_encoder.encode(text)
            joint = state.hippocampus.bind({"text": vec})
            state.hippocampus.store_episode(
                key=key, content=text, joint_vector=joint, modalities=["text"],
                source=source, activation=0.5, meta={"ok": result.ok, **result.meta})
        except Exception as exc:  # noqa: BLE001 — keep the heartbeat beating
            print(f"[tools] episode store error: {exc}")
    return True
