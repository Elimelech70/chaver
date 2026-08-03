"""Telnet chat front end — converse with the running Chaver over telnet.

A line-based asyncio server. Each connected client speaks to the *same*
Chaver as the stdin console: one working memory, one hippocampus, one
continuous self. Turns from every transport share a monotonic turn counter
and a lock (passed in from the heartbeat), so nothing interleaves.

Design discipline:
- No cognition here. This module reads lines and writes lines; all thinking
  happens through the shared handle_turn (CLAUDE.md principle 8).
- No extra language calls on connect — a static banner greets the client so
  the language faculty stays disciplined (principle 2). The human speaks
  first.
- Errors are swallowed per-connection; a dropped client never stops the
  heartbeat (the "keep beating" rule).

Telnet note: this speaks enough of the protocol to be usable from a raw
`telnet host port` client — it filters out IAC negotiation sequences and
translates newlines — without pulling in the deprecated stdlib telnet
modules. It is plaintext and unauthenticated; bind it to localhost (the
default) and reach it over an SSH tunnel for anything but local use.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Iterator

# IAC (Interpret As Command) and the negotiation verbs that follow it.
_IAC = 255
_SB, _SE = 250, 240
_NEGOTIATION = {251, 252, 253, 254}  # WILL, WONT, DO, DONT — each + 1 option

BANNER = (
    "\r\n"
    "  Chaver — companion, one bound-together.\r\n"
    "  You are speaking with the running mind, not a fresh session.\r\n"
    "  Type a line and press Enter. '/quit' to leave; he stays awake.\r\n"
    "\r\n"
)

# The signature of chaver.heartbeat.handle_turn, passed in to avoid a circular
# import (heartbeat imports this module).
TurnHandler = Callable[..., Awaitable[str]]


def _strip_telnet(raw: bytes) -> str:
    """Drop IAC negotiation sequences and decode the human-typed remainder."""
    out = bytearray()
    i, n = 0, len(raw)
    while i < n:
        b = raw[i]
        if b == _IAC:
            nxt = raw[i + 1] if i + 1 < n else 0
            if nxt in _NEGOTIATION:
                i += 3  # IAC + verb + option
                continue
            if nxt == _SB:  # subnegotiation: skip to IAC SE
                j = i + 2
                while j < n and not (raw[j] == _IAC and j + 1 < n and raw[j + 1] == _SE):
                    j += 1
                i = j + 2
                continue
            i += 2  # IAC + some other 2-byte command
            continue
        out.append(b)
        i += 1
    return out.decode("utf-8", errors="ignore")


async def serve_telnet(
    state,
    language,
    handle_turn: TurnHandler,
    turn_counter: Iterator[int],
    turn_lock: asyncio.Lock,
    host: str = "127.0.0.1",
    port: int = 8023,
) -> None:
    """Run the telnet chat server until state.running goes false.

    Args:
        state: The shared ChaverState.
        language: The language faculty (passed straight through to handle_turn).
        handle_turn: chaver.heartbeat.handle_turn — the transport-agnostic turn.
        turn_counter: Shared monotonic turn id source (itertools.count).
        turn_lock: Shared lock serialising turns across transports.
        host: Bind address. Default localhost — do not expose plaintext widely.
        port: Bind port. 8023 by default (23 needs root).
    """

    async def handle_client(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        peer = writer.get_extra_info("peername")

        def send(text: str) -> None:
            # telnet expects CRLF line endings
            writer.write(text.replace("\n", "\r\n").encode("utf-8", "ignore"))

        try:
            send(BANNER)
            await writer.drain()
            while state.running:
                writer.write(b"> ")
                await writer.drain()
                raw = await reader.readline()
                if not raw:  # client closed
                    break
                user_text = _strip_telnet(raw).strip()
                if not user_text:
                    continue
                if user_text.lower() in ("/quit", "/exit", "/bye"):
                    send("\nChaver: I'll be here. Go well.\n")
                    await writer.drain()
                    break

                turn = next(turn_counter)
                try:
                    reply = await handle_turn(
                        state, language, user_text, turn, turn_lock
                    )
                except Exception as exc:  # noqa: BLE001 — keep the mind alive
                    reply = f"[error this turn: {exc}]"
                send(f"\nChaver: {reply}\n\n")
                await writer.drain()
        except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError):
            pass
        except Exception as exc:  # noqa: BLE001
            print(f"[telnet client {peer} error] {exc}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass

    try:
        server = await asyncio.start_server(handle_client, host, port)
    except OSError as exc:
        print(f"[telnet] could not bind {host}:{port} — {exc}")
        return

    async with server:
        # Serve until the agent is going to sleep, then close cleanly.
        while state.running:
            await asyncio.sleep(0.5)
        server.close()
        try:
            await server.wait_closed()
        except Exception:  # noqa: BLE001
            pass
