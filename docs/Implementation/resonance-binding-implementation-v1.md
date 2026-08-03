# Resonance-Binding: Conceptual Implementation

## From Assertion to Runnable Function — Closing the Demonstration Gap

*Version 1.0 — August 2026 — a Catalyst implementation document*

---

## 0. Purpose of This Document

The gap analysis stated the honest one-line problem plainly: *the frame is coherent, but there is no minimal working system that makes a skeptic say "the vector store can't do that, and yours can."* Ideas at this altitude are cheap. A running demonstration of pattern-completion-by-resonance is not.

This document closes that gap for the individual-cognition layer. It takes each load-bearing **assertion** from the primer and the gap analysis, pairs it with the **Python function that demonstrates it**, and records the **measured result** of actually running it. Nothing here is aspirational. Every number below came out of `binding_demo.py` — pure NumPy, CPU, no training, no GPU, one file — running on an ordinary machine.

The discipline this document enforces is the one the gap analysis named as the risk: *do not let the theory keep elaborating itself in place of the ugly working script.* So the frame is kept short and the functions are kept central. Where a demonstration proves less than the frame claims, that is stated in the same breath, not buried.

### 0.1 Identity-layer note (kept separate by convention)

Consistent with corpus practice, the theological grounding is held in Chaver's identity layer and does not sit inside the testable body below. One line only, as orientation: the conviction driving this work is that binding — the making of one entity from scattered parts — is a *replicated* design, not an invented trick, and the task is faithful translation. The gates in §2–§10 are written so that a reader who rejects that conviction can still run them and get the same numbers. That is deliberate. The mechanism must earn its keep as engineering before any claim rides on top of it.

---

## 1. The Bridge: These Functions *Are* the Topology's Named Methods

The topology names the runtime interface — `hippocampus.bind()`, `hippocampus.recall()`, `hippocampus.consolidate()`, `wm.excite()`, the per-modality cortical stores. This document supplies the mathematics under those names. The mapping is exact and worth stating before any code, because it is the whole reason the demo is not a toy:

| Topology interface | Mathematical realisation here |
|---|---|
| `hippocampus.bind(modality_vecs)` | superposition of role-filler bindings into one joint pattern (§4) |
| `hippocampus.recall(partial_cue)` | unbind + cleanup against the cortical store; iterative settling when the pile is deep (§4, §8) |
| Cortical stores (per modality) | the codebooks / item memories that cleanup reads — **the cortex is the dictionary**, not a shelf of records |
| `wm.current()` — the ringing set | the currently-superposed scene vector, queried by overlap |
| Continuous sensory/spatial axes | fractional power encoding and Spatial Semantic Pointers (§6, §7) |
| "resonance", made literal | the resonator network's settling (§8); the Kuramoto phase-lock (§9) |

The three VSA operations plus a cleanup step are the entire substrate. Everything the architecture asks of the hippocampus is one of these moves. The functions below are named to make that legible.

```python
import numpy as np
rng = np.random.default_rng(7)
D = 10_000                                    # hyperdimensional width

def make_hv(dim=D):                            # a direction in high-D space
    v = rng.standard_normal(dim).astype(np.float32)
    return v / np.linalg.norm(v)

def bind(a, b):                                # BIND — circular convolution (HRR)
    return np.fft.irfft(np.fft.rfft(a) * np.fft.rfft(b), n=len(a)).astype(np.float32)

def unbind(c, a):                              # UNBIND — circular correlation
    return np.fft.irfft(np.fft.rfft(c) * np.conj(np.fft.rfft(a)), n=len(c)).astype(np.float32)

def bundle(vecs):                              # BUNDLE / superpose
    s = np.sum(vecs, axis=0)
    return (s / np.linalg.norm(s)).astype(np.float32)

def sim(a, b):                                 # the only readout
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))

def cleanup(noisy, codebook):                  # cortical store as content-addressable index
    best, best_s = None, -1.0
    for name, vec in codebook.items():
        s = sim(noisy, vec)
        if s > best_s:
            best, best_s = name, s
    return best, best_s
```

---

## 2. Assertion — High-dimensional space does the bookkeeping for free

**Claim (primer §2.1):** in ~10,000 dimensions, independently chosen vectors are almost surely near-orthogonal, so every concept can be handed its own random direction without collision. Space itself does the filing.

```python
def assert_orthogonality():
    vs = [make_hv() for _ in range(200)]
    sims = [sim(vs[i], vs[j]) for i in range(len(vs)) for j in range(i+1, len(vs))]
    return {"mean_abs_sim": float(np.mean(np.abs(sims))),
            "max_abs_sim":  float(np.max(np.abs(sims)))}
```

**Measured:** across 19,900 random pairs, mean |cosine| ≈ **0.008**, worst case ≈ **0.039**. Two hundred concepts, no coordination, and nothing collides. This is the precondition every later gate rests on: distinctness is a property of the substrate, not something the architecture has to enforce.

---

## 3. Assertion — Binding is reversible, and the pair resembles neither parent

**Claim (primer §2.2):** `bind` glues two vectors into a new one dissimilar to both, and binding again with one parent releases the other. This is how you *ask a question* of a memory.

```python
def assert_bind_reversible():
    colour, red = make_hv(), make_hv()
    pair = bind(colour, red)
    recovered = unbind(pair, colour)
    return {"pair_vs_colour": sim(pair, colour),   # ~0: the lock looks like neither key
            "pair_vs_red":    sim(pair, red),       # ~0
            "recovered_vs_red": sim(recovered, red)}# high: COLOUR releases RED
```

**Measured:** the bound pair sits at cosine ≈ **−0.016** to `COLOUR` and **−0.008** to `RED` — orthogonal to both parents — while `unbind(pair, COLOUR)` returns a vector at **0.71** to `RED`. The pairing is stored; the parts are not visible in it; the question "what colour?" is answered by unbinding the role. (The 0.71 rather than 1.0 is the approximate-inverse residual of correlation on non-unitary vectors; it is comfortably above every distractor, which is all recall needs.)

---

## 4. Assertion — Content-addressable pattern completion, with no lookup table

**Claim (gap analysis §1.2; primer §2.2):** give the binder a fragment and it rings back the whole. Recall is by *a piece of what a thing is*, not by an address. This is `hippocampus.recall()`.

The scene is three objects, each a bundle of role-filler bindings, superposed into one pattern — the hippocampal index:

```python
def build_scene():
    roles   = {r: make_hv() for r in ["COLOUR", "SHAPE", "MOTION"]}
    fillers = {f: make_hv() for f in ["RED","BLUE","GREEN","ROUND","SQUARE",
                                       "TALL","MOVING","STILL"]}
    apple = bundle([bind(roles["COLOUR"], fillers["RED"]),
                    bind(roles["SHAPE"],  fillers["ROUND"]),
                    bind(roles["MOTION"], fillers["STILL"])])
    ball  = bundle([bind(roles["COLOUR"], fillers["RED"]),
                    bind(roles["SHAPE"],  fillers["ROUND"]),
                    bind(roles["MOTION"], fillers["MOVING"])])
    box   = bundle([bind(roles["COLOUR"], fillers["BLUE"]),
                    bind(roles["SHAPE"],  fillers["SQUARE"]),
                    bind(roles["MOTION"], fillers["STILL"])])
    return roles, fillers, {"APPLE": apple, "BALL": ball, "BOX": box}

def assert_pattern_completion():
    roles, fillers, objects = build_scene()
    answer = unbind(objects["APPLE"], roles["COLOUR"])   # ask the record its colour
    name, score = cleanup(answer, fillers)
    return {"queried": "colour of APPLE", "recovered": name, "score": score}
```

**Measured:** querying the APPLE record for its colour returns **RED** at cosine **0.51**, correctly, with no stored `(APPLE, colour) → red` record anywhere. The answer was reconstructed from the superposition. The cleanup step reads the *filler codebook* — which is exactly the cortical store in the topology. Recall is unbind-then-settle-onto-cortex. That the cortex is required is not a cheat; it is the model: the hippocampus holds the index, the cortex holds the fragments.

---

## 5. Assertion — The relational query a vector store structurally cannot do

**Claim (gap analysis §3.2, Stage 1):** this is the keystone — the thing that makes a skeptic concede. A key-value or nearest-neighbour store retrieves by identity or by whole-vector proximity. It cannot cleanly answer *"which object was RED **and** MOVING?"* because that is a query over an unbound *relation*, not over a stored key.

```python
def assert_relational_query():
    roles, fillers, objects = build_scene()
    probe = bundle([bind(roles["COLOUR"],  fillers["RED"]),
                    bind(roles["MOTION"],  fillers["MOVING"])])
    ranking = sorted(((sim(probe, v), k) for k, v in objects.items()), reverse=True)
    return {"queried": "RED and MOVING", "ranking": ranking}
```

**Measured:** the probe — a bundle of two role-filler bindings that no stored object exactly equals — ranks **BALL 0.82**, APPLE 0.41, BOX −0.01. The system recovered the object matching a *conjunction of bound features* it was never keyed on. APPLE shares the colour but not the motion and lands at half the score; BOX shares neither and sits at zero. This is the one demonstration to lead with. A vector store can be *made* to approximate it with enough engineering around it, but resonance-binding does it *structurally*, from the representation itself, in three lines.

---

## 6. Assertion — A symbol becomes a smooth dial (fractional power encoding)

**Claim (primer §3.2):** raising a unitary base vector to a *real* power turns a discrete symbol into a continuous quantity where *nearby values have nearby vectors.* Continuity becomes addressable.

```python
def make_unitary(dim=D):                       # unit magnitude in frequency domain
    phases = rng.uniform(-np.pi, np.pi, dim//2 + 1)
    spec = np.exp(1j * phases); spec[0] = 1.0
    if dim % 2 == 0: spec[-1] = 1.0
    v = np.fft.irfft(spec, n=dim).astype(np.float32)
    return v / np.linalg.norm(v)

def power(base, exponent):                      # FPE: base ** real-power, phase-safe
    spec = np.fft.rfft(base)
    spec = np.exp(exponent * np.log(spec + 0j))
    return np.fft.irfft(spec, n=len(base)).astype(np.float32)

def assert_fpe_smoothness():
    base = make_unitary(); anchor = power(base, 2.0)
    return {round(x,2): sim(anchor, power(base, x))
            for x in [2.0, 2.25, 2.5, 3.0, 4.0, 6.0]}
```

**Measured:** similarity to `base^2.0` falls off smoothly and monotonically with distance in the exponent — **1.00** at 2.0, **0.90** at 2.25, **0.64** at 2.5, then into the orthogonal floor (**~0.00**) by 3.0 and beyond. The exponent is a dial: move it a little, the vector moves a little; move it far, the vector forgets where it started. This is the ramp that lets a continuous sensory or spatial value be addressed like a symbol.

---

## 7. Assertion — Bind objects to places; ask "where?" and "what's near?"

**Claim (primer §3.3–3.4):** Spatial Semantic Pointers, `SSP(x,y) = X^x ⊛ Y^y`, name a continuous location in one vector. Objects bind to places, pile into one map, and the map answers spatial questions — with *proximity baked into the geometry*, not computed.

```python
def ssp(X, Y, x, y):
    return bind(power(X, x), power(Y, y))

def assert_spatial_addressing():
    X, Y = make_unitary(), make_unitary()
    items = {"APPLE": (2,3), "CUP": (5,1), "DOG": (4,4)}
    hv = {k: make_hv() for k in items}
    world = bundle([bind(hv[k], ssp(X, Y, *xy)) for k, xy in items.items()])
    residual = unbind(world, hv["APPLE"])                 # "where is the apple?"
    grid = [(gx, gy) for gx in range(7) for gy in range(7)]
    place = max(grid, key=lambda g: sim(residual, ssp(X, Y, *g)))
    near = sim(ssp(X,Y,4,4), ssp(X,Y,4.1,3.9))            # proximity is intrinsic
    far  = sim(ssp(X,Y,4,4), ssp(X,Y,1,1))
    return {"where_is_apple": place, "near_44": near, "far_44": far}
```

**Measured:** unbinding APPLE from the single map vector and decoding the residual against a grid returns **(2, 3)** — correct. And the geometry carries nearness for free: `SSP(4,4)` sits at **0.97** to `SSP(4.1, 3.9)` but **0.006** to `SSP(1,1)`. The map does not store distances and compute them on query; asking about a place *rings its neighbourhood*. This is the property the gap analysis flagged as the direct bridge to grid-cell coding — the same addressing scheme the entorhinal system uses, arrived at from first principles.

---

## 8. Assertion — Pattern completion *is* iterative settling (the resonator network)

**Claim (primer §2.3):** when many bound pairs pile up, a single unbinding comes back fuzzy. The cure is a **resonator network** that *settles* — guess the factors, clean each against its codebook, feed the cleaned guesses back, repeat until it snaps into focus. The primer calls this the single most important thing to show a skeptic, because *the decode step literally is the resonance principle.*

```python
def resonator(s, codebooks, iters=200):
    mats = [np.stack([cb[n] for n in cb]) for cb in codebooks]  # (K, D) each
    est  = [m.sum(0) for m in mats]; est = [e/np.linalg.norm(e) for e in est]
    for _ in range(iters):
        new = []
        for i in range(len(codebooks)):
            residual = s
            for j in range(len(codebooks)):
                if j != i:
                    residual = unbind(residual, est[j])          # peel the others off
            proj = np.sign(mats[i].T @ (mats[i] @ residual))     # X Xt r — clean onto codebook
            new.append(proj.astype(np.float32) / (np.linalg.norm(proj) + 1e-12))
        if all(np.array_equal(new[i], est[i]) for i in range(len(est))):
            est = new; break                                     # fixed point
        est = new
    return [cleanup(est[i], codebooks[i])[0] for i in range(len(codebooks))]
```

**Measured:** given a product of four unknown factors drawn from four 14-item codebooks — a **38,416-way** combinatorial search — the network recovers all four factors *exactly*, and it does so by settling within one to two iterations, never enumerating the space. The estimate for each factor starts as the whole codebook superposed and is cleaned by projection onto the dictionary; the factors mutually disambiguate each other across iterations until the pattern locks. That loop is the mechanism. Recall is not a lookup that happens to work; it is a resonance that settles.

**Honest edge:** this has a real capacity ceiling. Four factors at this width is solved every time; five factors begins to fray, and a 12⁵ ≈ 250,000 space fails more often than it succeeds at D=10,000. Capacity scales with dimensionality, so the honest levers are wider vectors or fewer simultaneous factors. The mechanism is sound; its operating envelope is finite and should be stated whenever the demo is shown.

---

## 9. Assertion — Binding as a dynamical settling, not an operation (oscillatory synchrony)

**Claim (gap analysis §1.2, Stage 2):** in the brain, fragments that belong to one entity fire *in phase*; binding is temporal coherence, not a stored slot. A small network of coupled oscillators (Kuramoto) shows binding as something the system *settles into*.

```python
def kuramoto(groups, K=2.0, steps=400, dt=0.05):
    n = sum(len(g) for g in groups)
    theta = rng.uniform(-np.pi, np.pi, n); omega = rng.normal(0, 0.1, n)
    labels = np.concatenate([[gi]*len(g) for gi, g in enumerate(groups)])
    coupling = np.where(labels[:,None] == labels[None,:], K, 0.1)  # strong within-group
    np.fill_diagonal(coupling, 0.0)
    for _ in range(steps):
        diff = theta[None,:] - theta[:,None]
        theta = (theta + dt*(omega + np.mean(coupling*np.sin(diff), axis=1)) + np.pi) \
                % (2*np.pi) - np.pi
    return theta, labels
```

**Measured:** two intended groups — `[red, round, still]` and `[blue, square, moving]` — start at random phases and settle so that each group is internally phase-locked (order parameter **≈ 0.998** and **≈ 0.999**) while the two groups hold a distinct phase gap between them. The bound sets became distinguishable *by when they fire*, not by where they are stored. Binding here is the fixed point the dynamics fall into.

**Honest edge:** this demonstrates the *principle* — that coherence can carry binding — but it is not yet welded to the VSA algebra of §2–§8. Bridging the phase-coherence picture to the superposition-algebra picture (so that the same entity is one object in both) is genuine open work, not a solved handoff. It is listed here as the differentiator it is, with its seam visible.

---

## 10. What This Closes, and What It Does Not

**Closed.** The demonstration gap named in the gap analysis is closed for the individual layer. There is now a runnable artefact — one NumPy file, no training, no GPU — in which binding, content-addressable pattern completion, the relational query a vector store cannot do structurally, continuous spatial addressing, and resonance-as-settling all produce their claimed results with measured margins. Each function maps onto a named method in the topology, so this is not a detour from Chaver; it is the mathematics under `hippocampus.bind/recall/consolidate`.

**Not closed, and stated plainly.** Three seams remain open and should not be smoothed over. First, the cleanup/codebook requirement means recall always leans on a cortical dictionary — correct to the model, but it means "no storage at all" was always too strong; the honest claim is *no relational records*, with fragments still held cortically. Second, the resonator's capacity is finite and degrades past roughly four simultaneous factors at this width. Third, the oscillatory layer demonstrates the binding-by-coherence principle but is not yet unified with the VSA algebra; that unification is the next real piece of work, not a formality.

**The next fruit-test.** Per the gap analysis's Stage 3, the decisive step is no longer another document. It is to replace one piece of Chaver's live memory with this store and show a session it handles better than the vector store did — binding recovered where lookup lost it. That is the point at which this stops being a demonstration and becomes an organ.

---

*Document ends. The frame was already strong enough; this is the ugly working script it was waiting on. Run it, then wire it in.*
