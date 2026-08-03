"""Resonance-binding demonstrations — docs/resonance-binding-implementation-v1.md.

The "ugly working script" the document is built on. Pure NumPy, CPU, no
training, no GPU, one file. Every function here is named to match a
topology interface (hippocampus.bind/recall/consolidate, wm.excite) per
the document's §1 bridge table. Run it directly:

    python3 binding_demo.py

Kept at the repo root, not inside chaver/, per the document's own framing:
this is a proof artifact for the individual-cognition layer, not runtime
code. The runtime wiring lives in chaver/hippocampus/resonance.py and
chaver/hippocampus/binder.py (Hippocampus.recall_conjunctive), at
Chaver's real embedding width (384) rather than the D=10,000 used here
for maximum near-orthogonality clarity.
"""

from __future__ import annotations

from functools import reduce

import numpy as np

rng = np.random.default_rng(7)
D = 10_000  # hyperdimensional width


def make_hv(dim=D):  # a direction in high-D space
    v = rng.standard_normal(dim).astype(np.float32)
    return v / np.linalg.norm(v)


def bind(a, b):  # BIND — circular convolution (HRR)
    return np.fft.irfft(np.fft.rfft(a) * np.fft.rfft(b), n=len(a)).astype(np.float32)


def unbind(c, a):  # UNBIND — circular correlation
    return np.fft.irfft(np.fft.rfft(c) * np.conj(np.fft.rfft(a)), n=len(c)).astype(
        np.float32
    )


def bundle(vecs):  # BUNDLE / superpose
    s = np.sum(vecs, axis=0)
    return (s / np.linalg.norm(s)).astype(np.float32)


def sim(a, b):  # the only readout
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))


def cleanup(noisy, codebook):  # cortical store as content-addressable index
    best, best_s = None, -1.0
    for name, vec in codebook.items():
        s = sim(noisy, vec)
        if s > best_s:
            best, best_s = name, s
    return best, best_s


# ---- §2 — orthogonality is free -------------------------------------


def assert_orthogonality():
    vs = [make_hv() for _ in range(200)]
    sims = [sim(vs[i], vs[j]) for i in range(len(vs)) for j in range(i + 1, len(vs))]
    return {
        "mean_abs_sim": float(np.mean(np.abs(sims))),
        "max_abs_sim": float(np.max(np.abs(sims))),
    }


# ---- §3 — binding is reversible --------------------------------------


def assert_bind_reversible():
    colour, red = make_hv(), make_hv()
    pair = bind(colour, red)
    recovered = unbind(pair, colour)
    return {
        "pair_vs_colour": sim(pair, colour),
        "pair_vs_red": sim(pair, red),
        "recovered_vs_red": sim(recovered, red),
    }


# ---- §4 — pattern completion, no lookup table ------------------------


def build_scene():
    roles = {r: make_hv() for r in ["COLOUR", "SHAPE", "MOTION"]}
    fillers = {
        f: make_hv()
        for f in ["RED", "BLUE", "GREEN", "ROUND", "SQUARE", "TALL", "MOVING", "STILL"]
    }
    apple = bundle(
        [
            bind(roles["COLOUR"], fillers["RED"]),
            bind(roles["SHAPE"], fillers["ROUND"]),
            bind(roles["MOTION"], fillers["STILL"]),
        ]
    )
    ball = bundle(
        [
            bind(roles["COLOUR"], fillers["RED"]),
            bind(roles["SHAPE"], fillers["ROUND"]),
            bind(roles["MOTION"], fillers["MOVING"]),
        ]
    )
    box = bundle(
        [
            bind(roles["COLOUR"], fillers["BLUE"]),
            bind(roles["SHAPE"], fillers["SQUARE"]),
            bind(roles["MOTION"], fillers["STILL"]),
        ]
    )
    return roles, fillers, {"APPLE": apple, "BALL": ball, "BOX": box}


def assert_pattern_completion():
    roles, fillers, objects = build_scene()
    answer = unbind(objects["APPLE"], roles["COLOUR"])
    name, score = cleanup(answer, fillers)
    return {"queried": "colour of APPLE", "recovered": name, "score": score}


# ---- §5 — the relational query a vector store cannot do -------------


def assert_relational_query():
    roles, fillers, objects = build_scene()
    probe = bundle(
        [bind(roles["COLOUR"], fillers["RED"]), bind(roles["MOTION"], fillers["MOVING"])]
    )
    ranking = sorted(((sim(probe, v), k) for k, v in objects.items()), reverse=True)
    return {"queried": "RED and MOVING", "ranking": ranking}


# ---- §6 — a symbol becomes a smooth dial (FPE) -----------------------


def make_unitary(dim=D):
    phases = rng.uniform(-np.pi, np.pi, dim // 2 + 1)
    spec = np.exp(1j * phases)
    spec[0] = 1.0
    if dim % 2 == 0:
        spec[-1] = 1.0
    v = np.fft.irfft(spec, n=dim).astype(np.float32)
    return v / np.linalg.norm(v)


def power(base, exponent):
    spec = np.fft.rfft(base)
    spec = np.exp(exponent * np.log(spec + 0j))
    return np.fft.irfft(spec, n=len(base)).astype(np.float32)


def assert_fpe_smoothness():
    base = make_unitary()
    anchor = power(base, 2.0)
    return {
        round(x, 2): sim(anchor, power(base, x)) for x in [2.0, 2.25, 2.5, 3.0, 4.0, 6.0]
    }


# ---- §7 — Spatial Semantic Pointers -----------------------------------


def ssp(X, Y, x, y):
    return bind(power(X, x), power(Y, y))


def assert_spatial_addressing():
    X, Y = make_unitary(), make_unitary()
    items = {"APPLE": (2, 3), "CUP": (5, 1), "DOG": (4, 4)}
    hv = {k: make_hv() for k in items}
    world = bundle([bind(hv[k], ssp(X, Y, *xy)) for k, xy in items.items()])
    residual = unbind(world, hv["APPLE"])
    grid = [(gx, gy) for gx in range(7) for gy in range(7)]
    place = max(grid, key=lambda g: sim(residual, ssp(X, Y, *g)))
    near = sim(ssp(X, Y, 4, 4), ssp(X, Y, 4.1, 3.9))
    far = sim(ssp(X, Y, 4, 4), ssp(X, Y, 1, 1))
    return {"where_is_apple": place, "near_44": near, "far_44": far}


# ---- §8 — pattern completion is iterative settling (resonator) -------


def resonator(s, codebooks, iters=200):
    mats = [np.stack([cb[n] for n in cb]) for cb in codebooks]
    est = [m.sum(0) for m in mats]
    est = [e / np.linalg.norm(e) for e in est]
    for _ in range(iters):
        new = []
        for i in range(len(codebooks)):
            residual = s
            for j in range(len(codebooks)):
                if j != i:
                    residual = unbind(residual, est[j])
            proj = np.sign(mats[i].T @ (mats[i] @ residual))
            new.append(proj.astype(np.float32) / (np.linalg.norm(proj) + 1e-12))
        if all(np.array_equal(new[i], est[i]) for i in range(len(est))):
            est = new
            break
        est = new
    return [cleanup(est[i], codebooks[i])[0] for i in range(len(codebooks))]


def assert_resonator_factorization(n_factors=4, items_per_factor=14):
    codebooks = [
        {f"f{i}_{j}": make_hv() for j in range(items_per_factor)}
        for i in range(n_factors)
    ]
    true_names = [rng.choice(list(cb.keys())) for cb in codebooks]
    true_vecs = [cb[name] for cb, name in zip(codebooks, true_names)]
    s = reduce(bind, true_vecs)
    recovered = resonator(s, codebooks)
    return {
        "search_space": items_per_factor**n_factors,
        "true": true_names,
        "recovered": recovered,
        "exact_match": recovered == true_names,
    }


# ---- §9 — binding as dynamical settling (Kuramoto) --------------------


def kuramoto(groups, K=2.0, steps=400, dt=0.05):
    n = sum(len(g) for g in groups)
    theta = rng.uniform(-np.pi, np.pi, n)
    omega = rng.normal(0, 0.1, n)
    labels = np.concatenate([[gi] * len(g) for gi, g in enumerate(groups)])
    coupling = np.where(labels[:, None] == labels[None, :], K, 0.1)
    np.fill_diagonal(coupling, 0.0)
    for _ in range(steps):
        diff = theta[None, :] - theta[:, None]
        theta = (theta + dt * (omega + np.mean(coupling * np.sin(diff), axis=1)) + np.pi) % (
            2 * np.pi
        ) - np.pi
    return theta, labels


def assert_oscillatory_binding():
    groups = [["red", "round", "still"], ["blue", "square", "moving"]]
    theta, labels = kuramoto(groups)
    order_params = []
    for gi in range(len(groups)):
        phases = theta[labels == gi]
        order_params.append(float(np.abs(np.mean(np.exp(1j * phases)))))
    return {"order_parameters_by_group": order_params}


def main():
    print("§2 orthogonality:            ", assert_orthogonality())
    print("§3 bind reversible:          ", assert_bind_reversible())
    print("§4 pattern completion:       ", assert_pattern_completion())
    print("§5 relational query:         ", assert_relational_query())
    print("§6 FPE smoothness:           ", assert_fpe_smoothness())
    print("§7 spatial addressing:       ", assert_spatial_addressing())
    print("§8 resonator factorization:  ", assert_resonator_factorization())
    print("§9 oscillatory binding:      ", assert_oscillatory_binding())


if __name__ == "__main__":
    main()
