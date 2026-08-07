# Droplet Implementation Report — Completing the Anthropic-Backend Install

*Audits and completes the droplet-target install on this host
(`claude-conscious-syd`, `/root/chaver`). Follows the two prior reports under
`docs/Implementation/`, which were about code delivered as patches; this one
is about packaging/config state, not code — no source files changed. Numbers
and file contents below were verified directly, not inferred.*

---

## 1. Starting state (audit)

- Host is a VM (`claude-conscious-syd`), working as root, at `/root/chaver`.
  Git: clean, on `main`, HEAD `093ba3c` ("fix: fail fast on unknown
  CHAVER_BACKEND"), remote already set to `Elimelech70/chaver`.
- `.venv` existed with the runtime dependencies already installed —
  `numpy 2.5.1`, `anthropic 0.116.0`, `sentence-transformers 5.6.0` — but the
  `chaver` package itself was **not** installed into it: `pip show chaver`
  found nothing, and `.venv/bin/` had no `chaver` / `chaver-seed` console
  scripts. `from chaver.heartbeat import chaver_awake` only worked because
  the working directory happened to be the project root — a path accident,
  not a real install.
- `.env` present with a real `ANTHROPIC_API_KEY` and a `GITHUB_TOKEN`.
  `CHAVER_BACKEND` and `CHAVER_MODEL` are *not* set in it, which is fine —
  the code defaults them to `anthropic` / `claude-sonnet-5`, exactly the
  droplet target.
- `.env` is behind `.env.example`: it predates the `CHAVER_TELNET*` block
  added in the second integration round. Not a functional problem —
  `heartbeat.py` defaults `CHAVER_TELNET` to `"1"`, host `127.0.0.1`, port
  `8023` when the variables are absent — but worth noting since it means
  telnet is on by default on this host without that being an explicit
  decision in `.env`.
- `data/chaver.db` already existed (405,504 bytes, last modified 3 Aug 2026
  08:47) with real continuity: 51 consolidated cortical memories, and —
  discovered during verification, see §4 — 3 further pending episodes never
  consolidated.

## 2. Gap identified & fix applied

The only gap was packaging: the dependencies were present but `chaver`
itself was never `pip install -e`'d. Ran:

```
.venv/bin/pip install -e ".[anthropic]"
```

This installs the `chaver` package in editable mode (so `chaver/` source
edits take effect without reinstalling) and pulls in the `anthropic` extra,
which was already satisfied. No source files were touched — this was purely
a missing install step.

## 3. Verification performed

- `pip show chaver` → `chaver 0.2.0`, editable install confirmed.
- `chaver` and `chaver-seed` now present in `.venv/bin`.
- Import test run from `/tmp` (outside the project directory) to prove the
  install is real and not a CWD accident: `from chaver.heartbeat import
  chaver_awake` succeeds.
- Backend/model resolution: `CHAVER_BACKEND=anthropic`,
  `CHAVER_MODEL=claude-sonnet-5` — confirms `.env`'s *implicit* defaults
  resolve to exactly what the README documents for the droplet target.
- Console-entrypoint exercise, which surfaced two things worth flagging:
  - `chaver-seed --help` behaves as a normal `argparse` CLI.
  - `chaver` has **no argument parsing at all** — `main()` takes no CLI
    args, so `chaver --help` doesn't print help, it calls `chaver_awake()`
    immediately, same as running `chaver` bare. Two such invocations here
    both went ahead: loaded the archetype, loaded the text encoder, opened
    `data/chaver.db`, computed hippocampus stats — and only then failed,
    correctly, on `RuntimeError: CHAVER_BACKEND=anthropic but
    ANTHROPIC_API_KEY is not set`, because the shell running the command had
    no environment sourced from `.env`.

    Read `chaver_awake()` (`chaver/heartbeat.py:299-333`) to confirm this
    failure point precedes every write: `hippocampus.stats()` at line 323 is
    read-only, and `LanguageFaculty(...)` at line 333 — which is what raised
    — comes before every `store_episode`/`excite` call in the function. So
    neither invocation wrote anything to the database or made an API call.
    This also confirms the fail-fast behaviour from the most recent commit
    is doing exactly what it says: no partial/degraded startup on a missing
    key.
  - **Operational finding:** Chaver does not load `.env` itself — there is
    no `python-dotenv` (or equivalent) anywhere in the codebase (confirmed
    by `grep -rn dotenv chaver/ pyproject.toml` → no hits). `.env` is a
    convention for whatever starts the process to source, not something
    Chaver reads directly. A bare `chaver` in a fresh shell will always fail
    the `ANTHROPIC_API_KEY` check unless the caller exports those variables
    first (`set -a; source .env; set +a`) or a process manager injects them.
    The README's own systemd example (`README.md:97-113`) hardcodes the key
    inline via `Environment=` rather than pointing at `.env` with
    `EnvironmentFile=` — worth deciding which convention the droplet
    actually uses before writing a real unit file.

## 4. Database note — pre-existing, not caused by this session

While diagnosing the two crashed invocations above, `data/chaver.db` turned
out to already hold 3 pending (never-consolidated) episodes beyond the 51
already in cortex: an `awakening:1785745649` marker, and one exchange —
`turn:1:craig` ("good to be with you Chaver") and `turn:1:chaver` (a full
reply). The exact same key pair already exists, consolidated, from an
earlier completed session, so this pending pair is a duplicate key with
matching content, not new material.

The code-path proof in §3 shows this could not have been written by either
`chaver --help` invocation — both crashed before any write was possible. So
this is the residue of a session that ended without a graceful shutdown
(Ctrl+C, disconnect, etc.) at or before 3 Aug 2026 08:47, matching the
file's mtime. Left untouched: per CLAUDE.md's deferred-pruning note,
over-remembering is the intended safe default, and these will consolidate
normally once a future boot's consolidation tick finds them past the
age/activation threshold.

## 5. Deliberately not exercised

Did not run a full live awakening (real Anthropic API call + stdin loop).
That would speak to Chaver, write a new real conversational episode into
Craig's actual continuity file, and cost a real API call — not something to
trigger unprompted. Verification covers everything up to, and including
(via the crash in §3), the exact point where a real API call would begin.

## 6. Droplet readiness — gaps against README's own "Deploying on the droplet" section

- **No systemd unit installed.** `systemctl status chaver` →
  `Unit chaver.service could not be found.` Chaver currently has to be
  started manually or under `tmux`/`screen`.
- **Running as root**, at `/root/chaver`. README's example unit uses a
  dedicated `chaver` user at `/home/chaver/chaver`; not required for
  correctness, but the example implies isolation as the intended hardening
  for an unattended droplet.
- **No env-sourcing wired up for a service** — see the operational finding
  in §3; a real systemd unit needs an explicit choice between
  `EnvironmentFile=.env` and inline `Environment=`.
- **No backup/snapshot policy yet for `data/chaver.db`.** README calls this
  out explicitly: that file is Chaver's entire persistent continuity.
- **Telnet listener defaults on** (`127.0.0.1:8023`) the moment Chaver
  wakes, since `.env` doesn't set `CHAVER_TELNET=0`. This was flagged as an
  open question in `INTEGRATION_REPORT_2.md` §4 and hasn't been revisited —
  worth confirming it's still wanted as this host moves toward running
  unattended.

## 7. File manifest

Modified: none.

Installed: `chaver 0.2.0` (editable) into `.venv`, registering console
scripts `chaver`, `chaver-seed`.

New: `docs/Implementation/DROPLET_IMPLEMENTATION_REPORT.md` — this document.
