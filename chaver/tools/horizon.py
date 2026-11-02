"""Catalyst Horizon tools: `horizon_read` and `horizon_publish`.

Both connect as `chaver_ro` (read all of `horizon`, INSERT only on `learning_notes` and
`principle_proposals`). The database role is the real guard; these tools add a second
one: reads are fixed, named queries (no free SQL), and publishing refuses every table
but the two. Connection settings come from the environment, never logged:
    CHAVER_HORIZON_DSN   e.g. postgresql://chaver_ro:...@host:25060/horizon?sslmode=require
(Replace with the read-only Horizon MCP server when it exists; same tool names.)
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from typing import Any

from chaver.tools.base import Tool, ToolResult

DSN_ENV = "CHAVER_HORIZON_DSN"
PUBLISH_TABLES = ("learning_notes", "principle_proposals")
NOTE_STATUSES = ("proposed", "testing", "validated", "refuted")
EVIDENCE_KEYS = ("sample_size", "window", "scope", "method")

# Named read-only queries. $1 = from date, $2 = to date (inclusive), $3 = row limit.
READ_QUERIES: dict[str, str] = {
    "trades": """
        SELECT * FROM horizon.trades
        WHERE trade_date BETWEEN $1 AND $2 ORDER BY trade_date, trade_id LIMIT $3""",
    "journal": """
        SELECT t.trade_id, t.trade_date, t.symbol, t.direction, t.tier, t.status, t.skip_reason,
               t.entry_price, t.exit_price, t.exit_reason, t.realized_pl, t.close_review,
               c.decided_by_principle, c.decided_by_version, th.confidence, th.principle_ids
        FROM horizon.trades t
        LEFT JOIN horizon.candidates c ON c.candidate_id = t.candidate_id
        LEFT JOIN horizon.theses th ON th.candidate_id = t.candidate_id
        WHERE t.trade_date BETWEEN $1 AND $2 ORDER BY t.trade_date, t.trade_id LIMIT $3""",
    "principle_applications": """
        SELECT pa.*, c.symbol, c.created_at
        FROM horizon.principle_applications pa
        JOIN horizon.candidates c ON c.candidate_id = pa.candidate_id
        WHERE c.created_at::date BETWEEN $1 AND $2 ORDER BY c.created_at LIMIT $3""",
    "principles": """
        SELECT * FROM horizon.selection_principles  -- all versions approved by `to` ($1 unused)
        WHERE $1::date IS NOT NULL AND coalesce(approved_on, $2::date) <= $2::date
        ORDER BY principle_id, version LIMIT $3""",
    "outcomes": """
        SELECT * FROM horizon.outcomes
        WHERE reference_at::date BETWEEN $1 AND $2 ORDER BY reference_at LIMIT $3""",
    "proposals": """
        SELECT * FROM horizon.principle_proposals
        WHERE proposed_at::date BETWEEN $1 AND $2 ORDER BY proposed_at LIMIT $3""",
    "learning_notes": """
        SELECT * FROM horizon.learning_notes
        WHERE created_at::date BETWEEN $1 AND $2 ORDER BY created_at LIMIT $3""",
    "kpi_values": """
        SELECT * FROM horizon.kpi_values
        WHERE created_at::date BETWEEN $1 AND $2 ORDER BY created_at LIMIT $3""",
}


def _jsonable(v: Any) -> Any:
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


async def _connect(dsn: str | None):
    import asyncpg  # only this package imports a database driver

    dsn = dsn or os.environ.get(DSN_ENV, "")
    if not dsn:
        raise RuntimeError(f"{DSN_ENV} is not set")
    return await asyncpg.connect(dsn)


class HorizonRead(Tool):
    """Read-only, named queries over the trader's journal."""

    name = "horizon_read"

    def __init__(self, dsn: str | None = None, max_rows: int = 500) -> None:
        self._dsn = dsn
        self._max_rows = max_rows

    async def call(self, args: dict[str, Any]) -> ToolResult:
        query = args.get("query", "")
        if query not in READ_QUERIES:
            return ToolResult.fail(f"unknown query '{query}'; known: {', '.join(READ_QUERIES)}")
        to_d = date.fromisoformat(args["to"]) if args.get("to") else date.today()
        from_d = date.fromisoformat(args["from"]) if args.get("from") else to_d - timedelta(days=7)
        limit = min(int(args.get("limit", self._max_rows)), self._max_rows)

        conn = await _connect(self._dsn)
        try:
            # A read-only transaction: a third guard on top of the role and the fixed SQL.
            async with conn.transaction(readonly=True):
                rows = await conn.fetch(READ_QUERIES[query], from_d, to_d, limit)
        except Exception as exc:  # noqa: BLE001 — e.g. table not there yet (sql/010)
            return ToolResult.fail(f"{query}: {type(exc).__name__}: {exc}", query=query)
        finally:
            await conn.close()

        data = [{k: _jsonable(v) for k, v in dict(r).items()} for r in rows]
        text = f"horizon_read {query} {from_d}..{to_d}: {len(data)} row(s)"
        return ToolResult(ok=True, text=text, data=data,
                          meta={"query": query, "from": str(from_d), "to": str(to_d), "rows": len(data)})


class HorizonPublish(Tool):
    """Publish a learning note or a principle proposal. Nothing else."""

    name = "horizon_publish"

    def __init__(self, dsn: str | None = None) -> None:
        self._dsn = dsn

    async def call(self, args: dict[str, Any]) -> ToolResult:
        table = args.get("table", "")
        if table not in PUBLISH_TABLES:
            # Second guard: refused here, before any connection is made.
            return ToolResult.fail(
                f"refused: horizon_publish writes only {' and '.join(PUBLISH_TABLES)}, not '{table}'",
                refused=True, table=table)
        row = args.get("row") or {}
        if table == "principle_proposals":
            return await self._proposal(row)
        return await self._note(row)

    async def _proposal(self, row: dict[str, Any]) -> ToolResult:
        evidence = row.get("evidence") or {}
        missing = [k for k in EVIDENCE_KEYS if k not in evidence]
        if missing:
            return ToolResult.fail(f"refused: evidence missing {', '.join(missing)}", refused=True)
        for k in ("principle_id", "from_version", "proposed"):
            if k not in row:
                return ToolResult.fail(f"refused: proposal missing '{k}'", refused=True)
        sql = """INSERT INTO horizon.principle_proposals
                     (principle_id, from_version, proposed, evidence, proposed_by)
                 VALUES ($1, $2, $3::jsonb, $4::jsonb, 'analyst') RETURNING proposal_id"""
        args = (row["principle_id"], int(row["from_version"]),
                json.dumps(row["proposed"]), json.dumps(evidence))
        return await self._insert("principle_proposals", sql, args)

    async def _note(self, row: dict[str, Any]) -> ToolResult:
        # Column names follow architecture v1.2 §4.13; align with sql/010_learning.sql when it lands.
        for k in ("title", "body", "data_basis"):
            if not row.get(k):
                return ToolResult.fail(f"refused: note missing '{k}'", refused=True)
        status = row.get("status", "proposed")
        if status not in NOTE_STATUSES:
            return ToolResult.fail(f"refused: status '{status}'", refused=True)
        sql = """INSERT INTO horizon.learning_notes
                     (author, title, body, data_basis, status, principles_informed)
                 VALUES ('analyst', $1, $2, $3::jsonb, $4, $5) RETURNING note_id"""
        args = (row["title"], row["body"], json.dumps(row["data_basis"]), status,
                list(row.get("principles_informed") or []))
        return await self._insert("learning_notes", sql, args)

    async def _insert(self, table: str, sql: str, args: tuple) -> ToolResult:
        conn = await _connect(self._dsn)
        try:
            new_id = await conn.fetchval(sql, *args)
        except Exception as exc:  # noqa: BLE001
            return ToolResult.fail(f"{table}: {type(exc).__name__}: {exc}", table=table)
        finally:
            await conn.close()
        return ToolResult(ok=True, text=f"published {table} #{new_id}", data={"id": new_id},
                          meta={"table": table, "id": new_id})
