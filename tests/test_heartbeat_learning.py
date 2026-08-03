"""Prove the heartbeat learns — acceptance test for 'an AI that thinks toward a
minimal fruit.'

A recurring moment R appears among random noise. Learning shows as:
  - R RECOGNITION rises: first sighting is a miss (novel), later sightings are
    caught from a partial cue — memory that predicts.
  - NOISE stays unrecognised: the agent doesn't hallucinate structure in noise.
  - The STORE PLATEAUS: reinforced R survives; noise fades and is pruned, so the
    episode count stops growing linearly.
CPU only, no LLM, no market.

Delivered as test_heartbeat_learning.py in docs/Implementation/Chaver
Implementation.zip, importing from a flat `chaver.*` namespace (`chaver.state`,
`chaver.heartbeat`, ...) that collides with the production package. Relocated
to tests/ and repointed at chaver.learning_core.* — see
docs/Implementation/INTEGRATION_REPORT.md. Test logic itself is unmodified.
"""
import asyncio
import numpy as np

from chaver.learning_core.evaluation import Evaluation
from chaver.learning_core.executive import Executive
from chaver.learning_core.heartbeat import Chaver
from chaver.learning_core.hippocampus.binder import ResonanceHippocampus
from chaver.learning_core.state import ChaverState
from chaver.learning_core.working_memory import RingingWorkingMemory

EMBED = 384
rng = np.random.default_rng(11)


def vec() -> np.ndarray:
    v = rng.standard_normal(EMBED).astype(np.float32)
    return v / np.linalg.norm(v)


R = {"text": vec(), "timeseries": vec(), "somatic": vec()}
P_RECUR = 0.3


def source() -> tuple[dict, str]:
    if rng.random() < P_RECUR:
        return R, "R"
    return {"text": vec(), "timeseries": vec(), "somatic": vec()}, "noise"


def recognition_rate(events, label):
    seen = [rec for (lab, rec) in events if lab == label]
    return (sum(seen) / len(seen)) if seen else 0.0


async def main() -> None:
    hc = ResonanceHippocampus(embed_dim=EMBED, bind_dim=10_000, seed=0)
    chaver = Chaver(
        hippocampus=hc, wm=RingingWorkingMemory(),
        executive=Executive("text"),
        evaluation=Evaluation(reward=0.25),      # gradual, so strength climbs visibly
        state=ChaverState(), source=source,
        tick_seconds=0.0, housekeeping_every=10, max_ticks=800,
        forget_decay=0.12,                        # noise fades within the run
    )
    await chaver.run()

    ev = chaver.events
    first_half, second_half = ev[:len(ev) // 2], ev[len(ev) // 2:]

    print(f"{'window':>10} {'R_recognised':>13} {'noise_FP':>9}")
    print(f"{'early':>10} {recognition_rate(first_half, 'R'):>13.2f} "
          f"{recognition_rate(first_half, 'noise'):>9.2f}")
    print(f"{'late':>10} {recognition_rate(second_half, 'R'):>13.2f} "
          f"{recognition_rate(second_half, 'noise'):>9.2f}")

    print(f"\n{'tick':>6} {'episodes':>9} {'R_strength':>11}")
    for h in chaver.history[::4]:
        print(f"{h['tick']:>6} {h['episodes']:>9} {h['r_strength']:>11}")

    r_late = recognition_rate(second_half, "R")
    noise_late = recognition_rate(second_half, "noise")
    peak = max(h["episodes"] for h in chaver.history)
    late_store = chaver.history[-1]["episodes"]

    learned = (
        r_late > 0.85              # recurrence reliably recognised from a fragment
        and noise_late < 0.05      # noise essentially never falsely recognised
        and late_store <= peak     # store plateaued — noise pruned, not hoarded
    )
    print(f"\nR recognised late: {r_late:.2f} | noise false-positive late: {noise_late:.2f}")
    print(f"store peak {peak} -> late {late_store} (plateau = pruning works)")
    print("\nLEARNING DEMONSTRATED" if learned else "\nNO LEARNING SIGNAL")
    assert learned, "learning core acceptance test failed its own success criteria"


if __name__ == "__main__":
    asyncio.run(main())
