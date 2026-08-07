"""Telegram chat transport — converse with the running Chaver via a Telegram bot.

Uses the Telegram Bot API with httpx long-polling (getUpdates). No webhook
server needed; Chaver initiates all outbound connections, which works behind
NAT and requires no port forwarding.

All turns from every transport share a monotonic turn counter and a lock
(passed in from the heartbeat), so nothing interleaves.

Design discipline:
- No cognition here. This module reads messages and sends replies; all
  thinking happens through the shared handle_turn (CLAUDE.md principle 8).
- No language calls on connection — there is no "connection" event in the
  poll model; the human speaks first.
- Allowlist is enforced before any turn is processed. Unrecognised senders
  are silently ignored; the transport fails closed (empty allowlist = no
  one gets through).
- Errors are swallowed per-update; a dropped message never stops the
  heartbeat (the "keep beating" rule).
- httpx is imported lazily so the module loads cleanly on deployments that
  haven't installed it (CLAUDE.md lazy-import convention).

Configuration (all via environment / .env):
    CHAVER_TELEGRAM=1                  Enable the transport (default: off)
    CHAVER_TELEGRAM_TOKEN=<token>      Bot token from @BotFather
    CHAVER_TELEGRAM_ALLOWLIST=<ids>    Comma-separated Telegram chat IDs;
                                       get yours from @userinfobot
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable
from typing import Iterator

# The signature of chaver.heartbeat.handle_turn, passed in to avoid a
# circular import (heartbeat imports this module).
TurnHandler = Callable[..., Awaitable[str]]

_API_BASE = "https://api.telegram.org/bot{token}"
_POLL_TIMEOUT = 30  # seconds — Telegram long-poll window


def _allowlist() -> frozenset[int]:
    """Parse CHAVER_TELEGRAM_ALLOWLIST into a frozen set of chat IDs."""
    raw = os.environ.get("CHAVER_TELEGRAM_ALLOWLIST", "").strip()
    if not raw:
        return frozenset()
    ids = set()
    for part in raw.split(","):
        part = part.strip()
        if part:
            try:
                ids.add(int(part))
            except ValueError:
                print(f"[telegram] ignoring non-integer allowlist entry: {part!r}")
    return frozenset(ids)


async def serve_telegram(
    state,
    language,
    handle_turn: TurnHandler,
    turn_counter: Iterator[int],
    turn_lock: asyncio.Lock,
) -> None:
    """Run the Telegram long-poll loop until state.running goes false.

    Args:
        state: The shared ChaverState.
        language: The language faculty (passed straight through to handle_turn).
        handle_turn: chaver.heartbeat.handle_turn — the transport-agnostic turn.
        turn_counter: Shared monotonic turn id source (itertools.count).
        turn_lock: Shared lock serialising turns across transports.
    """
    token = os.environ.get("CHAVER_TELEGRAM_TOKEN", "").strip()
    if not token:
        print("[telegram] CHAVER_TELEGRAM_TOKEN not set — transport disabled")
        return

    allowed = _allowlist()
    if not allowed:
        print(
            "[telegram] CHAVER_TELEGRAM_ALLOWLIST is empty — "
            "transport active but no senders will be processed (fails closed)"
        )

    try:
        import httpx  # lazy — not installed on every deployment target
    except ImportError:
        print(
            "[telegram] httpx not installed — "
            "run: pip install httpx   (or pip install -e '.[telegram]')"
        )
        return

    base = _API_BASE.format(token=token)
    offset = 0  # Telegram update_id offset; prevents re-delivering old messages

    print(f"[telegram] transport started — polling (allowlist: {sorted(allowed)})")

    async with httpx.AsyncClient(timeout=_POLL_TIMEOUT + 5) as client:
        while state.running:
            # ── Poll for new updates ──────────────────────────────────────────
            try:
                resp = await client.get(
                    f"{base}/getUpdates",
                    params={"offset": offset, "timeout": _POLL_TIMEOUT},
                )
                resp.raise_for_status()
                data = resp.json()
            except (httpx.HTTPError, Exception) as exc:  # noqa: BLE001
                print(f"[telegram] poll error: {exc}")
                await asyncio.sleep(2)  # back off briefly before retry
                continue

            if not data.get("ok"):
                print(f"[telegram] Telegram API error: {data}")
                await asyncio.sleep(2)
                continue

            updates = data.get("result", [])

            for update in updates:
                update_id = update.get("update_id", 0)
                offset = max(offset, update_id + 1)  # advance cursor

                message = update.get("message")
                if not message:
                    continue  # edited_message, channel_post, etc — skip

                chat_id = message.get("chat", {}).get("id")
                text = (message.get("text") or "").strip()

                if not text or chat_id is None:
                    continue

                # ── Allowlist enforcement — fails closed ──────────────────────
                if allowed and chat_id not in allowed:
                    # Silent ignore — do not leak information to unknown senders
                    continue

                if text.lower() in ("/quit", "/exit", "/bye"):
                    await _send(client, base, chat_id, "Understood. I'll be here.")
                    continue

                # ── Route through shared handle_turn ──────────────────────────
                turn = next(turn_counter)
                try:
                    reply = await handle_turn(
                        state, language, text, turn, turn_lock
                    )
                except Exception as exc:  # noqa: BLE001 — keep the mind alive
                    reply = f"[error this turn: {exc}]"

                await _send(client, base, chat_id, reply)

            # If no updates arrived (empty poll), loop immediately.
            # If updates arrived, give the event loop a moment before next poll.
            if updates:
                await asyncio.sleep(0.1)


async def _send(client, base: str, chat_id: int, text: str) -> None:
    """Send a message to a Telegram chat, swallowing errors."""
    try:
        resp = await client.post(
            f"{base}/sendMessage",
            json={"chat_id": chat_id, "text": text},
        )
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        print(f"[telegram] send error to {chat_id}: {exc}")
