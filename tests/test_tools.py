"""Tools layer (analyst implementation M5).

Database tests run on a THROWAWAY Postgres with the Horizon schema and roles. They are
skipped unless these are set:
    CHAVER_TEST_PG_HOST     Unix-socket dir (or host) of a disposable server; superuser `postgres`, trust auth
    CHAVER_TEST_HORIZON_SQL Catalyst-Horizon `sql/` dir (001..009 and 002_roles.sql)
Each run drops and recreates database `chaver_tools_test`. Never point these at a real server.
"""
from __future__ import annotations

import ast
import asyncio
import os
import subprocess
from pathlib import Path

import pytest

from chaver.state import ChaverState
from chaver.tools.base import Tool, ToolRegistry, ToolResult
from chaver.tools.field import ingest
from chaver.tools.horizon import HorizonPublish, HorizonRead, READ_QUERIES
from chaver.tools.report import ReportWrite
from chaver.working_memory.ringing import WorkingMemory

ROOT = Path(__file__).resolve().parent.parent
PG_HOST = os.environ.get("CHAVER_TEST_PG_HOST", "")
SQL_DIR = os.environ.get("CHAVER_TEST_HORIZON_SQL", "")
DB = "chaver_tools_test"
needs_pg = pytest.mark.skipif(not (PG_HOST and SQL_DIR), reason="no throwaway Postgres configured")

# Stand-in for the learning_notes part of Horizon's sql/010_learning.sql (not on main yet):
# columns from architecture v1.2 §4.13; grants as trader-learning-loop step 3.
STAND_IN_010 = """
SET search_path TO horizon;
CREATE TABLE IF NOT EXISTS learning_notes (
    note_id BIGSERIAL PRIMARY KEY,
    author TEXT NOT NULL CHECK (author IN ('trader','analyst')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    title TEXT NOT NULL, body TEXT NOT NULL,
    data_basis JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed','testing','validated','refuted')),
    principles_informed TEXT[] NOT NULL DEFAULT '{}',
    adopted_by TEXT[] NOT NULL DEFAULT '{}'
);
GRANT SELECT, INSERT ON learning_notes TO chaver_ro;
GRANT USAGE ON SEQUENCE learning_notes_note_id_seq TO chaver_ro;
ALTER TABLE principle_proposals DROP CONSTRAINT IF EXISTS principle_proposals_decision_check;
"""
SQL_ORDER = ["001_schema", "003_phase2", "004_daily_report", "005_execution", "006_spread_record_only",
             "007_rvol_v2", "008_chain_priority", "009_get_trading", "002_roles"]


def _psql(db: str, *args: str) -> str:
    return subprocess.run(["psql", "-h", PG_HOST, "-U", "postgres", "-d", db, "-q", "-v", "ON_ERROR_STOP=1",
                           "-At", *args], check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture(scope="module")
def horizon_db():
    _psql("postgres", "-c", f"DROP DATABASE IF EXISTS {DB}")
    _psql("postgres", "-c", f"CREATE DATABASE {DB}")
    for name in SQL_ORDER:
        _psql(DB, "-f", str(Path(SQL_DIR) / f"{name}.sql"))
    _psql(DB, "-c", STAND_IN_010)
    _psql(DB, "-c", """SET search_path TO horizon;
        INSERT INTO cycles (cycle_id, trigger_type) VALUES ('c1', 'manual');
        INSERT INTO candidates (candidate_id, cycle_id, symbol, reached_step, outcome) VALUES (1, 'c1', 'ABC', 'rank', 'proposed');
        INSERT INTO principle_applications (candidate_id, principle_id, version, result) VALUES (1, 'P-THS-04', 1, 'pass');
        INSERT INTO trades (trade_date, cycle_id, candidate_id, symbol, direction, tier, status, client_order_id)
            VALUES (current_date, 'c1', 1, 'ABC', 'long', 'paper', 'closed', 'co-1');""")
    yield f"postgresql://chaver_ro@/{DB}?host={PG_HOST}"


def _counts(tables: list[str]) -> dict[str, str]:
    return {t: _psql(DB, "-c", f"SELECT count(*) FROM horizon.{t}") for t in tables}


JOURNAL = ["trades", "candidates", "principle_applications", "selection_principles", "cycles", "orders",
           "fills", "positions", "outcomes", "theses", "proposals"]


# ── Reads ────────────────────────────────────────────────────────────────────

@needs_pg
@pytest.mark.parametrize("query", ["trades", "journal", "principle_applications", "principles",
                                   "outcomes", "proposals", "learning_notes"])
def test_reads(horizon_db, query):
    r = asyncio.run(HorizonRead(dsn=horizon_db).call({"query": query}))
    assert r.ok, r.error
    if query in ("trades", "journal", "principle_applications"):
        assert r.meta["rows"] == 1 and r.data[0]["symbol"] == "ABC"


@needs_pg
def test_read_missing_table_is_a_result_not_a_crash(horizon_db):
    r = asyncio.run(HorizonRead(dsn=horizon_db).call({"query": "kpi_values"}))  # sql/010 not applied
    assert not r.ok and "kpi_values" in r.error


def test_read_unknown_query_refused():
    r = asyncio.run(HorizonRead(dsn="postgresql://unused").call({"query": "DROP TABLE trades"}))
    assert not r.ok and "unknown query" in r.error


# ── Publish: the two allowed tables ──────────────────────────────────────────

@needs_pg
def test_publish_note_and_proposal(horizon_db):
    before = _counts(JOURNAL)
    pub = HorizonPublish(dsn=horizon_db)
    note = asyncio.run(pub.call({"table": "learning_notes", "row": {
        "title": "t", "body": "b", "data_basis": {"trades": [1]}, "principles_informed": ["P-THS-04"]}}))
    assert note.ok, note.error
    prop = asyncio.run(pub.call({"table": "principle_proposals", "row": {
        "principle_id": "P-THS-04", "from_version": 1, "proposed": {"statement": "x"},
        "evidence": {"sample_size": 30, "window": "2026-10", "scope": {"market": "US"}, "method": "paper"}}}))
    assert prop.ok, prop.error
    assert _psql(DB, "-c", "SELECT author FROM horizon.learning_notes") == "analyst"
    assert _psql(DB, "-c", "SELECT proposed_by FROM horizon.principle_proposals") == "analyst"
    assert _counts(JOURNAL) == before  # nothing else written


@needs_pg
def test_proposal_without_evidence_refused(horizon_db):
    r = asyncio.run(HorizonPublish(dsn=horizon_db).call({"table": "principle_proposals", "row": {
        "principle_id": "P", "from_version": 1, "proposed": {}, "evidence": {"sample_size": 3}}}))
    assert not r.ok and "evidence missing" in r.error


# ── Refusal paths: the tool AND the database ─────────────────────────────────

@pytest.mark.parametrize("table", ["trades", "orders", "selection_principles", "positions", ""])
def test_tool_refuses_other_tables(table):
    # Refused before any connection: the DSN is unusable on purpose.
    r = asyncio.run(HorizonPublish(dsn="postgresql://nobody@/none?host=/nonexistent").call(
        {"table": table, "row": {"symbol": "X"}}))
    assert not r.ok and r.error.startswith("refused") and r.meta.get("refused")


@needs_pg
@pytest.mark.parametrize("sql", [
    "INSERT INTO horizon.trades (trade_date, cycle_id, symbol, direction, tier, status, client_order_id) "
    "VALUES (current_date, 'c1', 'X', 'long', 'paper', 'closed', 'co-x')",
    "UPDATE horizon.selection_principles SET statement = 'x'",
    "DELETE FROM horizon.principle_proposals",
    "UPDATE horizon.learning_notes SET status = 'validated'",
])
def test_database_refuses_chaver_ro(horizon_db, sql):
    import asyncpg

    async def attempt():
        conn = await asyncpg.connect(horizon_db)
        try:
            await conn.execute(sql)
        finally:
            await conn.close()
    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        asyncio.run(attempt())


# ── report_write, on a temporary repo with a temporary remote ────────────────

def test_report_write(tmp_path):
    remote, repo = tmp_path / "remote.git", tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "clone", "-q", str(remote), str(repo)], check=True, capture_output=True)
    for k, v in (("user.name", "t"), ("user.email", "t@t")):
        subprocess.run(["git", "-C", str(repo), "config", k, v], check=True)
    r = asyncio.run(ReportWrite(repo=repo, push=True).call({"date": "2026-11-03", "body": "# Report"}))
    assert r.ok, r.error
    assert (repo / "reports/analyst/2026-11-03.md").read_text() == "# Report\n"
    log = subprocess.run(["git", "-C", str(remote), "log", "--format=%s", "main"],
                         capture_output=True, text=True, check=True).stdout
    assert "Analyst report 2026-11-03" in log
    r2 = asyncio.run(ReportWrite(repo=repo, push=False).call({"date": "2026-11-03", "body": "more"}))
    assert r2.ok and not r2.data["pushed"]
    assert asyncio.run(ReportWrite(repo=repo).call({"body": ""})).error.startswith("refused")


def test_report_push_off_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("CHAVER_REPORT_PUSH", raising=False)
    assert ReportWrite(repo=tmp_path)._push is False


# ── Results enter through the field ──────────────────────────────────────────

class _Echo(Tool):
    name = "echo"

    async def call(self, args):
        return ToolResult(ok=True, text=f"echo {args.get('x')}", meta={"x": args.get("x")})


class _Boom(Tool):
    name = "boom"

    async def call(self, args):
        raise ValueError("bad")


class _FakeEncoder:
    def encode(self, text):
        import numpy as np
        return np.ones(4, dtype="float32") / 2


class _FakeHippocampus:
    def __init__(self):
        self.episodes = []

    def bind(self, vecs):
        return vecs["text"]

    def store_episode(self, **kw):
        self.episodes.append(kw)
        return len(self.episodes)


def test_results_enter_through_the_field():
    reg = ToolRegistry()
    reg.register(_Echo())
    reg.register(_Boom())
    hc = _FakeHippocampus()
    state = ChaverState(archetype=None, working_memory=WorkingMemory(),
                        hippocampus=hc, text_encoder=_FakeEncoder())
    ok = asyncio.run(reg.call("echo", {"x": 1}))
    bad = asyncio.run(reg.call("boom"))
    assert ok.ok and not bad.ok and "ValueError" in bad.error  # a failing tool doesn't raise
    assert ingest(state, "echo", ok) and ingest(state, "boom", bad)
    assert [e["source"] for e in hc.episodes] == ["tool:echo", "tool:boom"]
    assert hc.episodes[0]["content"] == "echo 1"


# ── Nothing in the cognitive stack bypasses the layer ────────────────────────

def test_only_tools_import_db_or_http_clients():
    banned = {"asyncpg", "psycopg", "psycopg2", "sqlalchemy"}
    offenders = []
    for py in (ROOT / "chaver").rglob("*.py"):
        if "tools" in py.relative_to(ROOT / "chaver").parts:
            continue
        for node in ast.walk(ast.parse(py.read_text())):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            offenders += [f"{py.name}:{n}" for n in names if n.split(".")[0] in banned]
    assert offenders == []
    cognitive = (ROOT / "chaver" / "cognitive")
    for py in cognitive.rglob("*.py"):
        assert "chaver.tools.horizon" not in py.read_text()


def test_read_queries_are_select_only():
    for name, sql in READ_QUERIES.items():
        assert sql.strip().upper().startswith("SELECT"), name
        assert ";" not in sql, name
