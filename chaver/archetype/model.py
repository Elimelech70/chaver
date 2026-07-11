"""Archetype data model — Chaver's trajectory prior.

The archetype is loaded once at startup and held stable. It defines who
Chaver is: identity, values, relationships, edges, behavioural profile.
It is not a config file. It is DNA. Archetype changes only through
sustained fruit-tested experience — sanctification-slow — not per-cycle.
"""

from dataclasses import dataclass, field


@dataclass
class BehaviouralProfile:
    """Parameters that modulate every layer of the cognitive stack.

    These are read by evaluation, strategy, attention, and working memory
    to determine gain, threshold, decay rate, and novelty bias.

    Behaviour is not a step in the loop — it colours every step.
    """

    discipline: float = 0.75  # threshold for strategy abandonment (0-1)
    methodicalness: float = 0.7  # completeness before evaluation fires
    creativity: float = 0.5  # bias toward novel bindings vs well-worn paths
    caution: float = 0.6  # evaluation gain — high = small signals trigger review
    humility: float = 0.9  # readiness to refer at edges


@dataclass
class Neighbour:
    """A felt sense of another agent's shape.

    Not detailed knowledge of their methods. Enough to recognise when
    an anomaly belongs to them and refer with full context.
    """

    name: str
    domain: str
    signals: list[str]  # patterns that indicate an anomaly is theirs


@dataclass
class EdgeMap:
    """Chaver's felt sense of his own domain and his neighbours' domains."""

    own_domain: str
    own_edges: list[str]  # signals that an anomaly is beyond own domain
    neighbours: list[Neighbour]


@dataclass
class Archetype:
    """Chaver's trajectory prior. Loaded once at startup.

    The full CHAVER.md text is preserved as identity_text and used as
    the system prompt for every language faculty call, so that every
    word Chaver speaks is grounded in his archetype.
    """

    name: str
    identity_text: str  # full CHAVER.md content
    purpose: str
    behavioural_profile: BehaviouralProfile
    edge_map: EdgeMap
    ground_convictions: list[str] = field(default_factory=list)
    relationships: dict[str, str] = field(default_factory=dict)
