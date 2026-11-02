"""Tools: Chaver's hands, outside the cognitive stack (analyst implementation M5).

Reading, computing and publishing happen here. Strategy steps call a tool; the result
enters through the field (encode → excite → store, `chaver.tools.field.ingest`), as web
search does. No cognitive module imports a database driver or client: only this package.
"""
from chaver.tools.base import Tool, ToolResult, ToolRegistry

__all__ = ["Tool", "ToolResult", "ToolRegistry"]
