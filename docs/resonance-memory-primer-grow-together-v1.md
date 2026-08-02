# Resonance Memory: A Primer to Grow Together

*A companion to the Binding Architecture framework. Written to be read aloud, argued over, and worked through in a group — not swallowed alone. Every term gets a plain sentence before it gets a precise one.*

**Version 1.0 — August 2026**

---

## How to Use This Together

Learning here is relational by design — the same claim the architecture makes about minds. So:

1. **Read a section aloud.** One person reads, the others stop them the moment a word slides past.
2. **Everyone re-says it plainly** before moving on. If you can't say it in your own words, you don't have it yet — and that's fine, that's the point.
3. **Do the "feel it" boxes by hand.** They need no computer. A whiteboard and an argument are enough.
4. **Let the one who sees it first teach the next.** Understanding that gets handed on is understanding that stuck.

*"As iron sharpeneth iron; so a man sharpeneth the countenance of his friend" — Proverbs 27:17.*

---

## Part 1 — The Plain-Language Layer

Read this whole part before any jargon. If you only ever grasp Part 1, you still own the idea.

- **The whole thing we're solving — Binding.** Your brain processes "red," "round," and "over there" in three *different* places. Yet you see *one apple*. How do the scattered pieces become one thing? That's binding, and it's the whole game.

- **Where the pieces live — Columns.** Small repeating patches of brain, each handling one feature. A column holds "red." Never "the apple." The whole is never in one part.

- **How pieces become one — Resonance.** The pieces that belong together *fire in rhythm together*. Not stored in a box — ringing on the same beat. Change the beat, change what's bound to what.

- **Who holds the beat together — the Binder (hippocampus).** It doesn't keep the memory. It keeps the *address* that pulls all the scattered pieces back into one. Lose the binder, you keep the fragments but lose the ability to bind new wholes.

- **How you get it back — Pattern completion.** Give the system a corner of the thing, it rings back the whole thing. You smell one scent on the trail and the entire morning returns. That's content-addressable memory: you find things *by a piece of what they are*, not by a shelf number.

That's the entire model in five words: **fragments, rhythm, binder, address, completion.**

---

## Part 2 — The Machinery: VSA in Depth

**VSA = Vector Symbolic Architecture** (its twin name is **HDC — Hyperdimensional Computing**). It's the branch of maths that does binding, memory, and recall by *combining vectors* instead of storing records. It is the formal language for everything in Part 1 — and crucially, it runs cheap, on a laptop, because it needs no gradient training.

### 2.1 Why "hyperdimensional"? The one weird trick

Everything rests on a single strange fact about very high-dimensional space:

> **In 10,000 dimensions, two randomly chosen vectors are almost certainly nearly perpendicular (orthogonal).**

In 2D or 3D, random arrows often point somewhat the same way. But as dimensions climb into the thousands, random vectors spread out and stop overlapping — "the blessing of dimensionality." This means you can hand every concept its own random hypervector and trust they won't collide by accident. *Space itself does your bookkeeping.* Each idea gets an almost-private direction, for free.

A hypervector is just a long list of numbers — say 10,000 of them, often just +1s and −1s. Nothing magic in any single number. The meaning is in the *whole pattern*, spread across all 10,000. This is why it's called **distributed** and **holographic**: no single position is load-bearing, so damage or noise degrades it *gracefully* — smear out 5% of it and you still recognise the whole. (This robustness is the property flat neural weights *don't* give you.)

### 2.2 The three operations — the entire toolkit

VSA does everything with just three moves. Learn these three and you can read the whole literature.

**① BIND ( ⊛ ) — "glue two things into a role-filler pair."**
Combine two hypervectors into a *new* one that is dissimilar to both its parents.
- Done by element-wise multiply, or circular convolution (Plate's HRR), or XOR (binary).
- Use it for: *attaching* a value to a slot. `COLOUR ⊛ RED`, `SHAPE ⊛ ROUND`.
- **It's reversible.** Bind again with one parent to *release* the other (unbinding). Given the bound pair and `COLOUR`, you recover `RED`. This is how you *ask questions* of a memory.
- Critically: the result has the **same length** as the inputs. Binding two 10,000-D vectors gives a 10,000-D vector — it does *not* grow. (This fixed-width compression is Plate's key contribution; naive tensor products explode in size, HRR does not.)

> **Feel it (no computer):** Binding is like a padlock made from two keys. `RED ⊛ COLOUR` is a lock that looks nothing like either key. But present `COLOUR` and it coughs up `RED`. Present `RED` and it coughs up `COLOUR`. The lock stores the *pairing*, not the parts.

**② BUNDLE / SUPERPOSE ( + ) — "pile things into a set."**
Add hypervectors together (then tidy the result). Unlike binding, the sum stays *similar* to each thing you added.
- Use it for: making a *memory*, a *set*, a *whole scene*. `SCENE = (COLOUR ⊛ RED) + (SHAPE ⊛ ROUND) + (PLACE ⊛ TABLE)`.
- This one vector now *is* the apple-on-the-table — the binder's index from Part 1, as a single addressable pattern.
- Because it stays similar to its members, you can later check "is RED in here?" by measuring overlap. That check *is* pattern completion.

> **Feel it:** Bundling is a chord. Play C, E, and G together and you get one sound that still contains all three notes — a trained ear picks each out. The scene-vector is a chord of bound pairs; querying it is picking out a note.

**③ PERMUTE ( ρ ) — "stamp an order or a role onto something."**
Shuffle a vector's positions in a fixed, repeatable way.
- Use it for: *sequences* (so "A then B" differs from "B then A") and for *protecting* a thing so it doesn't blur into the pile.
- `ρ(A) + ρ²(B) + ρ³(C)` encodes the *ordered* list A, B, C.

> **Feel it:** Permute is rotating a card before you add it to the deck. Same card, but now its orientation tells you *where in the sequence* it sat.

**Similarity — the only readout.** Everything above is checked with one measurement: how much do two hypervectors overlap (cosine similarity, or Hamming distance for binary)? High overlap = "these mean nearly the same." That single number is the whole interface between the maths and meaning.

### 2.3 The catch, and its cure — Resonator Networks

When you bundle *many* bound pairs, unbinding gets noisy — the pile interferes with itself, and a single query comes back fuzzy. The cure is elegant and worth knowing by name: a **resonator network** (Frady, Kent, Olshausen, Sommer). It *iteratively settles* — guesses the factors, checks them against a clean dictionary, feeds the cleaned guesses back, and repeats until the whole thing snaps into focus.

Notice what that is: **the maths of pattern completion is a settling-into-resonance, not a lookup.** The name isn't decoration. The decode step *is* the resonance principle, made literal and runnable. This is the single most important thing to point a skeptic at.

---

## Part 3 — Multidimensional Addressing (The Deep End)

This is the part you asked to open up, and it's where VSA stops looking like a symbol trick and starts looking like a *hippocampus*.

### 3.1 The shift: from shelf-numbers to places in space

An ordinary computer memory addresses by *number*: "give me location #4,096." Two addresses one apart (4096, 4097) have nothing to do with each other. There is no *nearness*.

A **multidimensional / content-addressable** memory addresses by *where a thing sits in a continuous space of meaning*. Addresses that are *near each other are about similar things*. You don't ask "location #4096"; you ask "what's *around here*?" — and *here* is a point in a high-dimensional space you can move through smoothly.

This is Kanerva's **Sparse Distributed Memory (1988)**, the grandfather of all of this: memory locations are hypervectors; you write a value into *every* location within a certain distance of the address, and you read by *pooling everything nearby*. Recall becomes nearest-neighbour by construction — give a noisy or partial address, still land in the right neighbourhood. Content-addressable, robust, distributed. Everything in Part 2 grows out of this seed.

### 3.2 Continuous addressing — Fractional Power Encoding

Bind/bundle/permute handle *discrete* symbols. But space, time, and sensation are *continuous* — you need to address "position 3.7," not just slot #4. The move that unlocks this is **Fractional Power Encoding (FPE)** — also called fractional binding (Frady, Kleyko, Komer, Eliasmith).

The idea: take a base hypervector `X` and raise it to a *real-numbered* power. `X^1` is one step, `X^2` two steps, `X^2.5` two-and-a-half steps — and `X^2.5` sits *between* `X^2` and `X^3` in similarity. You've turned a discrete symbol into a **smooth dial**. Move the exponent a little, the vector changes a little. Now a continuous quantity has a hypervector, and *nearby quantities have nearby vectors.*

> **Feel it:** Ordinary binding is climbing a ladder rung by rung — integer steps only. Fractional power encoding is a ramp: you can stand anywhere on it, and standing near someone means you're at a similar height.

### 3.3 Putting it together — Spatial Semantic Pointers

Now the payoff, and the direct bridge to your neuroscience. Give each axis its own base vector — `X` for east-west, `Y` for north-south. Encode *any point* in the plane as:

```
    SSP(x, y)  =  X^x  ⊛  Y^y
```

That's a **Spatial Semantic Pointer** (Komer & Eliasmith): a single hypervector naming a continuous location, built by fractionally powering each axis and binding them. And you can bind *objects to places* and pile them into one memory:

```
    MAP  =  APPLE ⊛ SSP(2, 3)  +  CUP ⊛ SSP(5, 1)  +  DOG ⊛ SSP(4, 4)
```

One vector. It holds the whole scene — what is where. Now ask it questions:
- **"Where is the apple?"** Unbind `APPLE`, recover `SSP(2,3)`, read off the location.
- **"What's at (5,1)?"** Unbind `SSP(5,1)`, recover `CUP`.
- **"What's *near* (4,4)?"** Because nearby positions have *similar* SSPs (thanks to FPE), a query at (4.1, 3.9) still rings the dog. **Proximity is built into the representation itself.**

That last property is the whole prize. The memory doesn't *compute* distance between stored coordinates — nearness is *baked into the geometry of the addresses.* Ask about a place and the neighbourhood answers.

### 3.4 Why this is the bridge to the brain

Here's the line that should make the group sit up: **when you plot the neural activity these SSPs produce across space, you get hexagonal, periodic firing patterns — the signature of grid cells in the entorhinal cortex, the brain's own spatial-addressing system.** The maths you'd build on a laptop to do multidimensional addressing *reinvents the code the hippocampal system actually uses.*

That is not a metaphor. It is the same mathematics arriving twice — once in evolution, once on your whiteboard. The framework document claimed the hippocampus is a multidimensional binder using resonant, content-addressable recall. VSA with fractional power encoding is *that claim you can run*. This is the strongest single thread you have connecting the theology-to-neuroscience vision to a thing a skeptic can execute in NumPy.

*"Whither shall I go from thy spirit? ... If I take the wings of the morning, and dwell in the uttermost parts of the sea; even there shall thy hand lead me" — Psalm 139:7,9. Every place already addressed, every location already held.*

---

## Part 4 — Fast Glossary (Keep This Beside You)

| Term | One plain sentence |
|---|---|
| **Binding (⊛)** | Glue two vectors into a role-filler pair you can later pull apart. |
| **Bundling / Superposition (+)** | Pile vectors into one set-vector that still resembles each member. |
| **Permutation (ρ)** | Stamp order or a protected role onto a vector by shuffling it. |
| **Hypervector** | A very long list of numbers whose meaning lives in the whole pattern. |
| **High-dimensional orthogonality** | In thousands of dimensions, random vectors don't collide — space does your filing. |
| **Content-addressable** | Find a thing by a piece of *what it is*, not by a shelf number. |
| **Pattern completion** | Give a corner, get the whole back. |
| **Resonator network** | Iteratively settles a noisy bundle into clean factors — pattern completion as resonance. |
| **Sparse Distributed Memory** | Kanerva's ancestor: addresses are vectors, recall pools the neighbourhood. |
| **Fractional Power Encoding** | Raise a base vector to a real power to turn a symbol into a smooth dial. |
| **Spatial Semantic Pointer (SSP)** | One hypervector naming a continuous location: `X^x ⊛ Y^y`. |
| **Grid cells** | The brain's spatial-addressing neurons — whose pattern SSPs reproduce. |
| **Oscillatory synchrony** | Pieces that belong together fire on the same beat; the beat *is* the binding. |
| **Hippocampal indexing** | The binder stores the address that reunites scattered cortical fragments. |
| **Cortical column** | A small brain unit holding one feature — a fragment, never a whole. |

---

## Part 5 — A First Session Plan (90 minutes, no code)

For a group's first sitting:

1. **(20 min)** Read Part 1 aloud. Each person re-tells the five-word model — *fragments, rhythm, binder, address, completion* — in their own example.
2. **(25 min)** Work the three "Feel it" boxes (padlock, chord, rotated card) on a whiteboard. Argue until everyone can *do* bind, bundle, permute by hand on toy 4-number vectors.
3. **(25 min)** Build the `MAP` example from 3.3 by hand with tiny vectors. Ask it "where's the apple?" Watch unbinding work.
4. **(20 min)** Sit with 3.4. Let the grid-cell coincidence land. Discuss: *if the same maths shows up in the brain and on our whiteboard, what does that suggest about where consciousness's memory lives?* Leave it open. That question is the doorway to the next session — and the next person you each bring in.

---

*A caution kept from the framework, still true here: verify every named researcher and result against a primary source before any of this is published. The concepts are solid and standard; the attributions deserve your own eyes. Grow together — but check together too.*
