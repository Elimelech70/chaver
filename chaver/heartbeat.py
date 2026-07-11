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
import signal as os_signal
import sys
from pathlib import Path

from chaver.archetype.loader import load_archetype
from chaver.cognitive.attention import Attention
from chaver.cognitive.behaviour import BehaviourModulator
from chaver.cognitive.evaluation import Evaluation
from chaver.cognitive.executive import Executive
from chaver.cognitive.strategy import StrategyLayer
from chaver.hippocampus.binder import Hippocampus
from chaver.language.faculty import LanguageFaculty, LanguageRequest
from chaver.persistence import close_db, open_db
from chaver.sensory.text_encoder import TextEncoder
from chaver.state import ChaverState
from chaver.working_memory.ringing import WorkingMemory


DEFAULT_DATA_DIR = Path("data")
DEFAULT_DB_NAME = "chaver.db"


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


def _excite_recall(state: ChaverState, cue_text: str, top_k: int = 4) -> int:
    """Recall memories cued by text and excite them into working memory.

    Returns the number of memories excited. Silently no-ops if the
    hippocampus or encoder isn't ready yet.
    """
    if state.hippocampus is None or state.text_encoder is None:
        return 0
    try:
        cue_vec = state.text_encoder.encode(cue_text)
        results = state.hippocampus.recall(cue_vec, top_k=top_k)
    except Exception as exc:  # noqa: BLE001
        print(f"[recall error] {exc}")
        return 0

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
    return len(results)


async def conversation_loop(
    state: ChaverState,
    language: LanguageFaculty,
) -> None:
    """Stdin conversation with Chaver — each turn becomes memory.

    Flow per turn:
      1. Craig speaks → text encoded.
      2. Hippocampus recalls memories resonant with the cue.
      3. Recalled memories excited in working memory.
      4. Language faculty called with full WM context.
      5. Response encoded, bound, stored as new episode.
      6. Both Craig's turn and Chaver's response persist as memory.
    """
    print("\n[Speak with Chaver. Empty line + Enter to send. Ctrl+C to end.]\n")

    loop = asyncio.get_running_loop()
    turn = 0

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

        turn += 1

        # Excite Craig's turn in WM.
        state.working_memory.excite(
            key=f"craig:turn:{turn}",
            content=user_text,
            source="craig",
            strength=0.95,
        )

        # Recall memories cued by Craig's words.
        recalled = _excite_recall(state, user_text, top_k=4)

        # Persist Craig's turn as an episode immediately so it becomes
        # part of Chaver's memory even if the response fails.
        if state.hippocampus is not None and state.text_encoder is not None:
            try:
                vec = state.text_encoder.encode(user_text)
                joint = state.hippocampus.bind({"text": vec})
                state.hippocampus.store_episode(
                    key=f"turn:{turn}:craig",
                    content=user_text,
                    joint_vector=joint,
                    modalities=["text"],
                    source="craig",
                    activation=0.7,
                    meta={"turn": turn, "speaker": "craig"},
                )
            except Exception as exc:  # noqa: BLE001
                print(f"[memory write error, craig turn] {exc}")

        # Generate response.
        try:
            reply = await language.generate(
                LanguageRequest(
                    prompt=user_text,
                    wm_context=state.working_memory.summary(),
                    purpose=(
                        f"conversation with Craig (turn {turn}; "
                        f"{recalled} memories recalled)"
                    ),
                    max_tokens=1024,
                )
            )
        except Exception as exc:  # noqa: BLE001
            print(f"\n[language faculty error: {exc}]\n")
            continue

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
        print(f"  [recalled {recalled} founding memories into working memory]")

    tasks = [
        asyncio.create_task(BehaviourModulator(state).run(), name="behaviour"),
        asyncio.create_task(Executive(state).run(), name="executive"),
        asyncio.create_task(StrategyLayer(state).run(), name="strategy"),
        asyncio.create_task(Attention(state).run(), name="attention"),
        asyncio.create_task(Evaluation(state).run(), name="evaluation"),
        asyncio.create_task(wm_decay_task(state), name="wm_decay"),
        asyncio.create_task(consolidation_task(state), name="consolidation"),
    ]

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
        conversation_loop(state, language),
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
