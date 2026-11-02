"""Tools registered from config (environment) at startup."""
from __future__ import annotations

import os

from chaver.tools.base import ToolRegistry
from chaver.tools.horizon import DSN_ENV, HorizonPublish, HorizonRead
from chaver.tools.report import ReportWrite


def tools_from_env() -> ToolRegistry:
    """Horizon tools only when CHAVER_HORIZON_DSN is set; report_write always."""
    reg = ToolRegistry()
    if os.environ.get(DSN_ENV):
        reg.register(HorizonRead())
        reg.register(HorizonPublish())
    reg.register(ReportWrite())
    return reg
