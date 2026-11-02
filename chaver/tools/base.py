"""Tool interface and registry."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """What a tool hands back. `text` is what enters the field; `data` is for code."""

    ok: bool
    text: str = ""
    data: Any = None
    error: str = ""
    meta: dict = field(default_factory=dict)

    @classmethod
    def fail(cls, error: str, **meta: Any) -> "ToolResult":
        return cls(ok=False, error=error, text=f"[tool error] {error}", meta=meta)


class Tool(ABC):
    """A small interface: a name and one async call."""

    name: str = ""

    @abstractmethod
    async def call(self, args: dict[str, Any]) -> ToolResult: ...


class ToolRegistry:
    """Tools registered by name (from config at startup)."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if not tool.name:
            raise ValueError("tool has no name")
        if tool.name in self._tools:
            raise ValueError(f"tool '{tool.name}' already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        return self._tools[name]

    @property
    def names(self) -> list[str]:
        return sorted(self._tools)

    async def call(self, name: str, args: dict[str, Any] | None = None) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult.fail(f"unknown tool '{name}'")
        try:
            return await tool.call(args or {})
        except Exception as exc:  # noqa: BLE001 — a tool failure must not stop the heartbeat
            return ToolResult.fail(f"{name}: {type(exc).__name__}: {exc}")
