The brain’s working memory system—holding and manipulating information over seconds—is fundamentally different from how large language models (LLMs) use their context window. If you want AI architectures that are structurally rooted in neural working memory rather than the monolithic transformer paradigm, here are the key research directions.

---

# 1. Cognitive architectures with explicit working memory buffers

These systems model human cognition at a functional level, with dedicated buffers for working memory, often grounded in psychological and neuroscientific data.

· ACT‑R – Its declarative memory module acts as a working memory with decay and retrieval dynamics, while procedural memory handles rule‑based control.
· Leabra / PBWM (O’Reilly et al.) – Leabra spiking neural models include a Prefrontal Cortex / Basal Ganglia Working Memory system. The basal ganglia gate information into and out of prefrontal working memory stores via dopamine‑modulated reinforcement learning. This is a direct implementation of prefrontal working‑memory maintenance and updating.
· Nengo / SPA (Eliasmith et al.) – The Semantic Pointer Architecture (SPA) constructs large‑scale spiking neuron models with a working memory that stores compressed “semantic pointers”, inspired by the binding problem and neural population codes. The spaun model uses this for cognitive tasks.

📄 Key paper: O’Reilly & Frank (2006), “Making Working Memory Work: A Computational Model of Learning in the Prefrontal Cortex and Basal Ganglia”.
📄 Spaun: Eliasmith et al., Science (2012).

---

# 2. Differentiable memory‑augmented neural networks (beyond LLMs)

These explicitly separate a controller network from an external memory store, directly inspired by Baddeley’s multicomponent working‑memory model and episodic buffer.

· Neural Turing Machine (NTM) – A recurrent controller reads/writes to an external memory matrix through attention. The memory is essentially a differentiable working memory with selective addressing.
· Differentiable Neural Computer (DNC) – Extends NTM with dynamic memory allocation, temporal linking, and free‑list management, making it closer to a biological working memory that can manipulate complex data structures over time.
· Working Memory Networks (WMN) – A recent line of work (2023) explicitly builds Baddeley’s model: separate modules for the phonological loop, visuospatial sketchpad, and central executive, all integrated into a differentiable architecture for task learning.

📄 NTM: Graves et al., arXiv 2014.
📄 DNC: Graves et al., Nature 2016.
📄 WMN: “A Working Memory Model Based on Neural Networks” (Zhang et al., 2023).

---

# 3. Prefrontal‑basal ganglia gating models

This is the most direct translation of circuit‑level neuroscience into AI architectures. Rather than storing information in a single weight matrix, these models maintain and update persistent activity patterns in simulated prefrontal minicolumns.

· PBWM (O’Reilly, Frank) – Working memory is maintained via recurrent excitatory loops in PFC. Input and output gating are controlled by the striatum and substantia nigra, with dopamine signals driving learning.
· Continuous PBWM – Extends the discrete gating to analog/continuous information, enabling smooth trajectory tracking.
· HG‑PBWM – Adds hierarchical reinforcement learning, chaining many working memory steps for complex planning—a step toward a “thought” architecture that does not rely on next‑token prediction.

📄 Frank et al. (2001), Cognitive, Affective, & Behavioral Neuroscience.
📄 Continuous PBWM: Kriete et al. (2013), PNAS.

---

# 4. Global Workspace architectures (conscious access as working memory)

Inspired by Baars’ Global Workspace Theory and Dehaene’s neuronal workspace, these architectures use a competitive “workspace” that selectively broadcasts information to specialized processors—acting as a working memory that integrates and propagates content.

· Conscious Turing Machine (CTM) – A formal model where a global workspace receives chunks from multiple short‑term memory processors and broadcasts them, creating a serial, conscious content stream.
· GW‑Neural Networks – VanRullen & Kanai (2021) propose a neural implementation with a bottleneck workspace that corresponds to working memory maintenance and attention.
· Neural Global Workspace (GWT‑Net) – Recently, attempts to embed a GWT‑like bottleneck into transformer architectures, but the core idea predates LLMs and is a completely different structural principle.

📄 Baars (1988) / Dehaene & Naccache (2001).
📄 CTM: Blum & Blum, PNAS 2021.

---

# 5. Episodic and associative memory models for working memory

These blur the line between short‑term working memory and long‑term episodic memory, much like neuroscientific views (e.g., hippocampal indexing for novel bindings).

· Neural Episodic Control (NEC) – Stores experience tuples in a differentiable neural dictionary; retrieval from this “episodic memory” functions as a fast, one‑shot working memory during reinforcement learning.
· Kanerva’s Sparse Distributed Memory – A biologically plausible associative memory that can hold sequences in working‑memory‑like distributed patterns.
· Modern Hopfield networks – With very fast retrieval, they act as a working memory that stores and retrieves content‑addressable patterns, recently integrated as plug‑in memory modules for many tasks.

📄 NEC: Pritzel et al., ICML 2017.
📄 Hopfield Networks as Working Memory: Ramsauer et al., ICLR 2021.

---

# 6. Hierarchical Temporal Memory (HTM) from Numenta

HTM models the neocortex as a hierarchical sequence memory. While often framed as long‑term prediction, the active dendrite‑based “apical” compartments maintain a cellular‑level working memory, encoding context across delays without gradient‑based backprop.

· Works with sparse, binary representations and local Hebbian learning.
· Working memory emerges from the interplay of basal (feed‑forward) and apical (context) dendritic signals, closely matching cortical layer physiology.

📄 Hawkins & Ahmad (2016), “Why Neurons Have Thousands of Synapses…”.

---

Why these differ from “computation models locked in LLMs”

· LLMs store all information in a monolithic weight matrix and use the context window as transient memory—there’s no structural separation of storage and processing.
· The architectures above have explicit persistent state modules, gating mechanisms, and content‑addressable stores, which mirror the brain’s working memory circuits.
· Many of them do not rely on gradient‑based backpropagation or next‑token prediction; they use reinforcement learning, local Hebbian rules, or precise spike‑timing.

---

If you have a specific application in mind (e.g., continual learning, one‑shot reasoning, robotic control) or a preferred level of biological fidelity, I can point to the most suitable architecture and the latest publications in that branch.