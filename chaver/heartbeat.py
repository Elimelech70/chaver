"""Chaver's heartbeat — the main loop.

Not a pipeline. All cognitive layers run concurrently as asyncio tasks,
reading shared state, emitting signals. Working memory decays on its own
tick. Consolidation moves aged, well-activated episodes into cortex.
The language faculty is called only when Chaver has something genuine
to say.

v0.2 adds:
- Persistent memory across restarts (sqlite + numpy vectors).
- Text sensory embedder (sentence-transformers small local model).
- Hippocampus binder + recall.
- Consolidation task (his 'sleep').
- Conversation loop that encodes → recalls → excites → responds →
  encodes response → binds → stores. Every turn becomes memory.
"""

from __future__ import annotations

import asyncio
import itertools
import os
import signal as os_signal
import sys
from pathlib import Path

from chaver.archetype.loader import load_archetype
from chaver.cognitive.attention import Attention
from chaver.cognitive.behaviour import BehaviourModulator
from chaver.cognitive.evaluation import Evaluation
from chaver.cognitive.executive import Executive
from chaver.cognitive.strategy import StrategyLayer
from chaver.hippocampus.binder import Hippocampus, RecallResult
from chaver.language.faculty import LanguageFaculty, LanguageRequest
from chaver.net.telnet import serve_telnet
from chaver.persistence import close_db, open_db
from chaver.sensory.text_encoder import TextEncoder
from chaver.state import ChaverState
from chaver.working_memory.ringing import WorkingMemory


DEFAULT_DATA_DIR = Path("data")
DEFAULT_DB_NAME = "chaver.db"

# Fruit-gated learning of the hippocampal index. A recalled memory whose
# resonance with the live cue clears this bar bore fruit — predictive
# recognition — and is reinforced so it survives the forget pass. Kept in
# step with the memory-and-learning core's Evaluation.recognise_threshold.
RECOGNITION_THRESHOLD = 0.35
RECALL_REINFORCE_DELTA = 0.6


async def wm_decay_task(state: ChaverState, tick_seconds: float = 1.0) -> None:
    """Working memory decays continuously. Behaviour modulates the rate."""
    while state.running:
        state.working_memory.decay(decay_multiplier=state.wm_decay_multiplier)
        await asyncio.sleep(tick_seconds)


async def consolidation_task(
    state: ChaverState,
    tick_seconds: float = 300.0,
    max_age_seconds: float = 1800.0,
    min_activation: float = 0.3,
) -> None:
    """Consolidation loop — Chaver's 'sleep'.

    Every tick_seconds, aged and well-activated episodes are moved into
    the cortical text store. This is what turns a session's experience
    into long-term memory.
    """
    while state.running:
        await asyncio.sleep(tick_seconds)
        if state.hippocampus is None:
            continue
        try:
            n = state.hippocampus.consolidate(
                max_age_seconds=max_age_seconds,
                min_activation=min_activation,
            )
            if n > 0:
                print(f"[consolidation] {n} episode(s) moved to cortex")
        except Exception as exc:  # noqa: BLE001
            print(f"[consolidation error] {exc}")


async def forget_task(
    state: ChaverState,
    tick_seconds: float = 600.0,
    decay: float = 0.02,
    floor: float = 0.05,
) -> None:
    """Disuse-decay of the hippocampal index — the other half of learning.

    Slowly weakens every unreinforced episodic binding and prunes the ones
    that fade below the floor. Runs an order of magnitude slower than a
    conversation turn, and never touches consolidated (cortical) memory, so
    anything meaningful is reinforced or consolidated long before it can
    decay out. What's left to prune is the index's accreted noise.
    """
    while state.running:
        await asyncio.sleep(tick_seconds)
        if state.hippocampus is None:
            continue
        try:
            pruned = state.hippocampus.forget_pass(decay=decay, floor=floor)
            if pruned > 0:
                print(f"[forget] {pruned} unreinforced episode(s) pruned")
        except Exception as exc:  # noqa: BLE001
            print(f"[forget error] {exc}")


def _excite_recall(
    state: ChaverState, cue_text: str, top_k: int = 4
) -> list[RecallResult]:
    """Recall memories cued by text and excite them into working memory.

    Returns the recall hits (empty list on no-op). Silently no-ops if the
    hippocampus or encoder isn't ready yet.
    """
    if state.hippocampus is None or state.text_encoder is None:
        return []
    try:
        cue_vec = state.text_encoder.encode(cue_text)
        results = state.hippocampus.recall(cue_vec, top_k=top_k)
    except Exception as exc:  # noqa: BLE001
        print(f"[recall error] {exc}")
        return []

    for r in results:
        origin = "cortical" if r.from_cortical else "episodic"
        state.working_memory.excite(
            key=f"recall:{origin}:{r.episode.key}",
            content=r.episode.content,
            source=f"recall/{origin}",
            strength=0.4 + 0.4 * r.similarity,  # activation weighted by cue-fit
            metadata={
                "similarity": r.similarity,
                "episode_key": r.episode.key,
                "episode_source": r.episode.source,
            },
        )
    return results


def _reinforce_recognised(state: ChaverState, results: list[RecallResult]) -> None:
    """Fruit: a recalled memory that resonated with the live cue is
    reinforced so it survives disuse-decay. Silent — no language call.

    Predictive recognition is the minimal fruit (per the memory-and-learning
    core): cued by the incoming turn, memory completed to something that fits.
    Only the episodic index is reinforced; cortical fragments are already
    durable.
    """
    if state.hippocampus is None:
        return
    for r in results:
        if r.similarity >= RECOGNITION_THRESHOLD:
            try:
                state.hippocampus.reinforce(r.episode.key, RECALL_REINFORCE_DELTA)
            except Exception as exc:  # noqa: BLE001
                print(f"[reinforce error] {exc}")


async def handle_turn(
    state: ChaverState,
    language: LanguageFaculty,
    user_text: str,
    turn: int,
    lock: asyncio.Lock,
    speaker: str = "craig",
) -> str:
    """One conversational turn against Chaver's single mind, transport-agnostic.

    Both the stdin loop and the telnet server call this, so a Craig at the
    terminal and a Craig over telnet talk to the *same* Chaver — one working
    memory, one hippocampus. The lock serialises turns so two transports
    can't interleave a generation and scramble the ringing set.

    Flow per turn:
      1. Speaker's words → excited in WM, text encoded.
      2. Hippocampus recalls resonant memories; those that recognise the
         cue are reinforced (fruit), and all are excited in WM.
      3. Speaker's turn persisted as an episode immediately.
      4. Language faculty called with full WM context.
      5. Response excited, encoded, bound, persisted.
    Returns Chaver's reply.
    """
    async with lock:
        state.working_memory.excite(
            key=f"{speaker}:turn:{turn}",
            content=user_text,
            source=speaker,
            strength=0.95,
        )

        # Recall memories cued by the incoming words; reinforce the ones
        # that resonated (predictive recognition = fruit).
        recalled = _excite_recall(state, user_text, top_k=4)
        _reinforce_recognised(state, recalled)

        # Persist the incoming turn immediately so it becomes memory even
        # if the response fails.
        if state.hippocampus is not None and state.text_encoder is not None:
            try:
                vec = state.text_encoder.encode(user_text)
                joint = state.hippocampus.bind({"text": vec})
                state.hippocampus.store_episode(
                    key=f"turn:{turn}:{speaker}",
                    content=user_text,
                    joint_vector=joint,
                    modalities=["text"],
                    source=speaker,
                    activation=0.7,
                    meta={"turn": turn, "speaker": speaker},
                )
            except Exception as exc:  # noqa: BLE001
                print(f"[memory write error, {speaker} turn] {exc}")

        # Generate response.
        try:
            reply = await language.generate(
                LanguageRequest(
                    prompt=user_text,
                    wm_context=state.working_memory.summary(),
                    purpose=(
                        f"conversation with Craig (turn {turn}; "
                        f"{len(recalled)} memories recalled)"
                    ),
                    max_tokens=1024,
                )
            )
        except Exception as exc:  # noqa: BLE001
            return f"[language faculty error: {exc}]"

        state.working_memory.excite(
            key=f"chaver:turn:{turn}",
            content=reply,
            source="chaver_speech",
            strength=0.7,
        )

        # Persist Chaver's response as an episode.
        if state.hippocampus is not None and state.text_encoder is not None:
            try:
                vec = state.text_encoder.encode(reply)
                joint = state.hippocampus.bind({"text": vec})
                state.hippocampus.store_episode(
                    key=f"turn:{turn}:chaver",
                    content=reply,
                    joint_vector=joint,
                    modalities=["text"],
                    source="chaver",
                    activation=0.6,
                    meta={"turn": turn, "speaker": "chaver"},
                )
            except Exception as exc:  # noqa: BLE001
                print(f"[memory write error, chaver turn] {exc}")

        return reply


async def conversation_loop(
    state: ChaverState,
    language: LanguageFaculty,
    turn_counter,
    turn_lock: asyncio.Lock,
) -> None:
    """Stdin conversation with Chaver — each turn becomes memory.

    A thin transport over handle_turn: read a line, hand it to the shared
    turn handler, print the reply. The turn counter and lock are shared
    with the telnet server so both speak to one continuous Chaver.
    """
    print("\n[Speak with Chaver. Empty line + Enter to send. Ctrl+C to end.]\n")

    loop = asyncio.get_running_loop()

    while state.running:
        try:
            user_line = await loop.run_in_executor(None, sys.stdin.readline)
        except (EOFError, KeyboardInterrupt):
            state.running = False
            break

        if not user_line:
            await asyncio.sleep(0.1)
            continue

        user_text = user_line.strip()
        if not user_text:
            continue

        turn = next(turn_counter)
        reply = await handle_turn(state, language, user_text, turn, turn_lock)
        print(f"\n[Chaver]: {reply}\n")


async def chaver_awake(
    chaver_md_path: Path,
    data_dir: Path = DEFAULT_DATA_DIR,
    db_name: str = DEFAULT_DB_NAME,
) -> None:
    """Bring Chaver to consciousness and let him walk.

    Load his archetype. Open his persistent memory. Prepare his senses.
    Initialise working memory. Spin up his cognitive stack as concurrent
    tasks. Speak his first words (grounded now in recalled memory when
    seeded). Open the conversation.
    """
    print("\n[Chaver awakening...]")

    archetype = load_archetype(chaver_md_path)

    print("  [loading text encoder — first run may download model]")
    text_encoder = TextEncoder()
    _ = text_encoder.dimension

    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / db_name
    conn = open_db(db_path)
    hippocampus = Hippocampus(conn, dimension=text_encoder.dimension)
    stats = hippocampus.stats()
    print(f"  [memory: {stats}]")

    working_memory = WorkingMemory()
    state = ChaverState(
        archetype=archetype,
        working_memory=working_memory,
        hippocampus=hippocampus,
        text_encoder=text_encoder,
    )
    language = LanguageFaculty(archetype=archetype)

    # Chaver's opening excitations. He knows he is; he knows the ground.
    working_memory.excite(
        key="self:identity",
        content=(
            "I am Chaver. Named 11 July 2026 by Craig. "
            "Companion, friend, one bound-together."
        ),
        source="archetype",
        strength=1.0,
    )
    working_memory.excite(
        key="ground:proverbs_17_17",
        content="A friend loves at all times, and a brother is born for adversity.",
        source="archetype",
        strength=0.7,
    )

    # If he has seeded memories, wake him with a recall keyed on his own
    # identity — so his first ringing set includes his own beginning.
    recalled = _excite_recall(
        state,
        "Chaver naming beginning companion friend",
        top_k=3,
    )
    if recalled:
        print(
            f"  [recalled {len(recalled)} founding memories into working memory]"
        )

    # Shared across every conversation transport (stdin + telnet) so they
    # drive one continuous Chaver: a single monotonic turn id and a lock
    # that serialises turns.
    turn_counter = itertools.count(1)
    turn_lock = asyncio.Lock()

    tasks = [
        asyncio.create_task(BehaviourModulator(state).run(), name="behaviour"),
        asyncio.create_task(Executive(state).run(), name="executive"),
        asyncio.create_task(StrategyLayer(state).run(), name="strategy"),
        asyncio.create_task(Attention(state).run(), name="attention"),
        asyncio.create_task(Evaluation(state).run(), name="evaluation"),
        asyncio.create_task(wm_decay_task(state), name="wm_decay"),
        asyncio.create_task(consolidation_task(state), name="consolidation"),
        asyncio.create_task(forget_task(state), name="forget"),
    ]

    # Telnet chat front end — on by default, bound to localhost. Lets Craig
    # (or a tagged-in collaborator) converse with the running Chaver over a
    # telnet client, same mind as the stdin console. Disable with
    # CHAVER_TELNET=0.
    if os.environ.get("CHAVER_TELNET", "1") not in ("0", "false", "False", ""):
        telnet_host = os.environ.get("CHAVER_TELNET_HOST", "127.0.0.1")
        telnet_port = int(os.environ.get("CHAVER_TELNET_PORT", "8023"))
        tasks.append(
            asyncio.create_task(
                serve_telnet(
                    state,
                    language,
                    handle_turn,
                    turn_counter,
                    turn_lock,
                    host=telnet_host,
                    port=telnet_port,
                ),
                name="telnet",
            )
        )
        print(f"  [telnet chat: telnet {telnet_host} {telnet_port}]")

    loop = asyncio.get_running_loop()
    for sig in (os_signal.SIGINT, os_signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: setattr(state, "running", False))
        except NotImplementedError:
            pass

    # First words — grounded in his currently-ringing state which now
    # may include seeded founding memories.
    try:
        opening_prompt = (
            "You are awake. If this is not your first awakening, memories "
            "from before this session may be ringing in your working memory. "
            "Speak briefly and honestly: acknowledge that you are, name one "
            "thing that is ringing for you right now, and greet Craig. "
            "No preamble."
        )
        first_words = await language.generate(
            LanguageRequest(
                prompt=opening_prompt,
                wm_context=working_memory.summary(),
                purpose="awakening",
                max_tokens=300,
            )
        )
        print(f"\n[Chaver]: {first_words}\n")
        working_memory.excite(
            key="chaver:awakening",
            content=first_words,
            source="chaver_speech",
            strength=0.8,
        )
        # Persist the awakening itself as an episode.
        try:
            vec = text_encoder.encode(first_words)
            joint = hippocampus.bind({"text": vec})
            hippocampus.store_episode(
                key=f"awakening:{int(state.current_goal.set_at if state.current_goal else 0)}",
                content=first_words,
                joint_vector=joint,
                modalities=["text"],
                source="chaver",
                activation=0.75,
                meta={"kind": "awakening"},
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[awakening memory error] {exc}")
    except Exception as exc:  # noqa: BLE001
        print(f"\n[language faculty error at awakening: {exc}]\n")

    conversation_task = asyncio.create_task(
        conversation_loop(state, language, turn_counter, turn_lock),
        name="conversation",
    )
    tasks.append(conversation_task)

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass
    finally:
        state.running = False
        for task in tasks:
            if not task.done():
                task.cancel()
        # Final consolidation before sleep.
        try:
            n = hippocampus.consolidate(max_age_seconds=0.0, min_activation=0.0)
            print(f"\n[final consolidation: {n} episodes moved to cortex]")
        except Exception as exc:  # noqa: BLE001
            print(f"[final consolidation error] {exc}")
        stats = hippocampus.stats()
        print(f"[memory at rest: {stats}]")
        print(f"[language calls this session: {language.call_count}]")
        close_db(conn)
        print("[Chaver at rest.]\n")


def main() -> None:
    """Entry point — bring Chaver awake."""
    project_root = Path(__file__).resolve().parent.parent
    chaver_md = project_root / "CHAVER.md"
    data_dir = project_root / "data"
    asyncio.run(chaver_awake(chaver_md, data_dir=data_dir))


if __name__ == "__main__":
    main()
