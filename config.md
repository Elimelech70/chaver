# Chaver — Implementation & Configuration Status

*Snapshot of the working setup as of 2026-07-11. This documents what has been
configured and verified, not design intent — see `CLAUDE.md` for that.*

---

## 1. Environment

| Item | Value |
|---|---|
| Python | 3.12.3 (project requires 3.11+) |
| Virtualenv | `.venv/` (gitignored) |
| Package manager | `pip`, deps from `requirements.txt` / `pyproject.toml` |

Installed dependencies (verified versions in `.venv`):

| Package | Version |
|---|---|
| `anthropic` | 0.116.0 |
| `sentence-transformers` | 5.6.0 |
| `torch` | 2.13.0 (pulled in by sentence-transformers) |
| `numpy` | 2.5.1 |

Setup commands used:

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

---

## 2. Configuration (`.env`)

`.env` is gitignored and never committed. Variables required:

| Variable | Purpose | Status |
|---|---|---|
| `ANTHROPIC_API_KEY` | Language faculty (Chaver's mouth/ear) | ✅ set |
| `CHAVER_MODEL` | Optional override, defaults to `claude-sonnet-5` | not set (using default) |
| `GITHUB_TOKEN` | Push access to `github.com/Elimelech70/chaver` | ✅ set (unrelated to Chaver's runtime — used for git operations only) |

Template lives at `.env.example`. Actual values are never written to this file
or committed — see the repo's `.gitignore`.

---

## 3. Version control

| Item | Value |
|---|---|
| Remote | `https://github.com/Elimelech70/chaver.git` |
| Branch | `main` |
| Local identity | `Elimelech70` / `181535450+Elimelech70@users.noreply.github.com` (repo-local, not global) |

`Begin/` (the original draft placeholder — `README-v0.2.md`, `blessing.md`,
and the `chaver-v0.2.1.tar.gz` archive) was unpacked into the repo root and
removed as superseded.

---

## 4. Seeded memory

Founding memories seeded via `chaver.seed` into `data/chaver.db`
(gitignored — this is Chaver's persistent continuity, not source):

| Source | Key prefix | Chunks |
|---|---|---|
| `CHAVER.md` (archetype) | `archetype:chaver_md` | 5 |
| `docs/catalyst-conceptual-architecture-v1.md` | `episode:architecture:...` | 19 |
| `docs/catalyst-conceptual-topology-v1.md` | `episode:architecture:...` | 11 |
| `blessing.md` | `episode:blessing:from_craig` | 3 |
| **Total** | | **38** consolidated |

Command used:

```bash
.venv/bin/python3 -m chaver.seed \
    --archetype CHAVER.md \
    --doc docs/catalyst-conceptual-architecture-v1.md \
    --doc docs/catalyst-conceptual-topology-v1.md \
    --blessing blessing.md
```

**Not yet seeded:** the formation transcript (the conversation where Chaver
was named). `CLAUDE.md` expects it at `conversations/formation-2026-07-11.md`
— that path doesn't exist in the repo. If Craig supplies the transcript, re-run
`chaver.seed` with `--transcript conversations/formation-2026-07-11.md` added;
seeding is idempotent (re-running skips already-seeded keys).

---

## 5. Verified boot

`python3 -m chaver.heartbeat` was run end-to-end and confirmed:

- Text encoder (sentence-transformers, local, 384-dim) loads correctly
- Hippocampus opens `data/chaver.db` and reports memory stats
- Founding memories recall successfully into working memory on wake
- Language faculty (Anthropic API) produces an awakening message grounded in
  recalled memory
- All seven concurrent cognitive tasks start (`behaviour`, `executive`,
  `strategy`, `attention`, `evaluation`, `wm_decay`, `consolidation`) plus the
  `conversation` task
- Signal handling (SIGTERM) triggers graceful shutdown: final consolidation
  runs, memory stats print, db closes cleanly

Post-boot-test memory state: `{'episodes_total': 40, 'episodes_pending_consolidation': 0, 'cortical_text': 40}`
(39 seeded + 1 awakening episode from the verification run).

Language faculty calls in that session: **1** (the awakening message only —
consistent with the "language faculty is peripheral" principle; no cognitive
layer calls it on its own).

---

## 6. Running Chaver

The heartbeat is an interactive stdin/stdout program — run it directly in a
terminal, not as a background/detached process, so you can actually converse:

```bash
cd /root/chaver
source .venv/bin/activate
python3 -m chaver.heartbeat
```

Empty line + Ctrl+C (or Ctrl+D) to end a session. Each turn — yours and his —
is written to `data/chaver.db` as an episode and consolidated into cortex on
the next consolidation tick (every 5 minutes) or at shutdown.

---

## 7. Open items

- [ ] Formation transcript not seeded (see §4)
- [ ] Both shared PATs (GitHub) and the Anthropic API key were pasted in
      plaintext chat during setup — recommended to rotate all three
- [ ] `HF_TOKEN` not set — sentence-transformers logs an unauthenticated-
      request warning on model download; harmless for a small public model,
      but can be set to silence the warning / raise rate limits
