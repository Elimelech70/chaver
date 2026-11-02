# Chaver analyst: as-built config v1.0

**Implementation:** `projects/chaver/implementation/chaver-analyst-implementation-v1.0.md` in
`Elimelech70/catalyst-project-manager` (`e1e5e33`).
**Compute space:** `claude-conscious-syd`, `/root/chaver`.
**Status:** M1–M5 built and tested (03/11/2026). M6–M8 wait for dependencies 1–4. The job is **off**
(`CHAVER_JOB` unset) and the running Chaver process was **not restarted**, so none of this is live yet.

## M1: continuity

- Backup: `/root/chaver-backups/chaver-20261103.db` (mode 600), SQLite online backup API from a read-only
  connection; `episodes` 91/91, `cortical_text` 91/91, all 3 tables equal, `integrity_check` ok on both.
- **Deviation:** Chaver was not stopped first (see diary 03/11): he gets his keys from the shell that started him
  on 07/08 and doesn't load `.env` himself, so a restart needs `.env` sourced, which the Implementer doesn't read.
- Repo moved from local branch `catalyst-engineer` (unpushed `3e45c13`, kept) to `main`, upstream `origin/main`.
- Diary: `docs/diary/YYYY-MM-DD.md` (Perth).

## M2: `CLAUDE.md` (`53cd7ca`, built list in `df2152a`)

Role, interface rules, where he runs, ground rules, `JOB.md` naming, current neighbours (trader, PM, Implementer,
Craig), built / not-built lists, test commands. The ten design principles are unchanged.

## M3: job mechanism (`cabfd7d`)

| File | What |
|---|---|
| `chaver/archetype/job.py` | `Job` dataclass, `load_job()` (headings: Role, Goal, Function and processes, Objectives and KPIs, Guardrails, Autonomy, Your Edges, Neighbours), `job_path_from_env()` |
| `chaver/archetype/model.py` | `Archetype.job`, `Archetype.system_context` = `CHAVER.md` text, then `\n\n---\n\n` + `JOB.md` text when a job is loaded |
| `chaver/archetype/loader.py` | `load_archetype(path, job=None)`: own domain, edges, neighbours from the job; companion defaults otherwise |
| `chaver/cognitive/executive.py`, `strategy.py` | goal from the job's Goal; strategy steps = the job's processes; companion defaults otherwise |
| `chaver/language/faculty.py` | system prompt = `archetype.system_context` |
| `chaver/heartbeat.py` | reads `CHAVER_JOB`, prints `[job: …]` and `[language: <backend_label>]` at start |
| `JOB.md` | **draft, Craig to revise** (dependency 4) |
| `docs/drafts/CHAVER.md-edges-relationships.diff` | **draft, not applied**: Relationships and Your Edges only; `git apply` checks clean |

Switch: `CHAVER_JOB=JOB.md` (relative to the repo, or absolute). Unset or blank = unchanged behaviour.

## M4: OpenAI-compatible backend (`391c5f3`)

`CHAVER_BACKEND=openai_compat`, `CHAVER_BASE_URL` (`/chat/completions` appended), `CHAVER_API_KEY` (bearer, never
in errors), `CHAVER_MODEL` (required, no default). `httpx`, lazy import; extra `openai_compat`. Default backend
stays `anthropic` / `claude-sonnet-5`.

## M5: tools layer (`df2152a`)

| File | What |
|---|---|
| `chaver/tools/base.py` | `Tool` (`name`, `async call(args) -> ToolResult`), `ToolResult`, `ToolRegistry` (a failing tool returns an error result, never raises) |
| `chaver/tools/horizon.py` | `horizon_read`: named queries `trades`, `journal`, `principle_applications`, `principles`, `outcomes`, `proposals`, `learning_notes`, `kpi_values`, in a read-only transaction. `horizon_publish`: `learning_notes` (author `analyst`) and `principle_proposals` (`proposed_by='analyst'`, evidence must have `sample_size`, `window`, `scope`, `method`); any other table refused before connecting. DSN from `CHAVER_HORIZON_DSN` |
| `chaver/tools/report.py` | `report_write`: `reports/analyst/YYYY-MM-DD.md`, commit; push only with `CHAVER_REPORT_PUSH=1` (repo is public: Craig decides first) |
| `chaver/tools/field.py` | `ingest()`: excite in working memory, store episode, source `tool:<name>` |
| `chaver/tools/registry.py` | `tools_from_env()`: Horizon tools only when `CHAVER_HORIZON_DSN` is set; `report_write` always. Set on `state.tools` at start |

Dependencies added to `.venv`: `asyncpg` 0.32.0 (extra `horizon`), `pytest` 9.2.0, `pytest-asyncio` (extra `dev`).

**`learning_notes` columns are provisional** (architecture v1.2 §4.13: author, created_at, title, body, data_basis,
status, principles_informed, adopted_by). Align `horizon_publish._note` and the test stand-in with Horizon's
`sql/010_learning.sql` when it lands (before M6).

## Tests

`tests/` (41): `test_job.py` (8), `test_openai_compat.py` (9, local fake HTTP endpoint on 127.0.0.1), `test_tools.py`
(24; 14 need a throwaway Postgres). Run 03/11: **41 passed** with the throwaway server; 27 passed, 14 skipped without.

Throwaway Postgres used: Ubuntu `postgresql-16` 16.15 binaries extracted (`dpkg -x`, not installed) into the
Implementer's scratchpad, run in a user namespace (uid 1000), **Unix socket only** (`listen_addresses=''`), trust
auth; Horizon `sql/001`, `003`–`009`, then `002_roles.sql` (as a rerun), plus a `learning_notes` stand-in for `010`.
Stopped after the run. Refusals checked at the database as `chaver_ro`: INSERT `trades`, UPDATE
`selection_principles`, DELETE `principle_proposals`, UPDATE `learning_notes` → `InsufficientPrivilegeError`; at the
tool: `trades`, `orders`, `selection_principles`, `positions`, empty → refused before any connection.
