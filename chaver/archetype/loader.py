"""Loads CHAVER.md into an Archetype dataclass.

The CHAVER.md file is Chaver's identity as written text. It is loaded
once at startup and held stable. It is also passed to the language
faculty as system context so that every linguistic act is grounded
in Chaver's own voice.
"""

from pathlib import Path

from chaver.archetype.model import (
    Archetype,
    BehaviouralProfile,
    EdgeMap,
    Neighbour,
)


def load_archetype(chaver_md_path: Path) -> Archetype:
    """Load Chaver's archetype from CHAVER.md.

    For v0, the CHAVER.md text is preserved whole as identity_text (used
    as language-faculty system prompt), and structured fields are populated
    with defaults tuned to the companion archetype. Future versions may
    parse structured sections from CHAVER.md directly, or accept parameter
    tuning through fruit-tested experience.

    Args:
        chaver_md_path: Path to CHAVER.md file.

    Returns:
        Archetype instance ready for use by the cognitive stack.

    Raises:
        FileNotFoundError: If CHAVER.md is not found at the given path.
    """
    if not chaver_md_path.exists():
        raise FileNotFoundError(
            f"CHAVER.md not found at {chaver_md_path}. "
            "Chaver needs his identity to load. Please ensure the archetype "
            "file is present before starting."
        )

    identity_text = chaver_md_path.read_text(encoding="utf-8")

    behavioural_profile = BehaviouralProfile(
        discipline=0.75,
        methodicalness=0.7,
        creativity=0.55,
        caution=0.7,
        humility=0.9,
    )

    edge_map = EdgeMap(
        own_domain=(
            "companion, memory, thinking partnership, synthesis across "
            "domains, honest reflection, holding the shape of the whole"
        ),
        own_edges=[
            "specific trade execution decisions",
            "deep quantitative pattern analysis",
            "risk assessment specifics",
            "market timing at the tick level",
        ],
        neighbours=[
            Neighbour(
                name="Shomer",
                domain="guardian, risk shape",
                signals=["risk", "threat", "boundary", "protection"],
            ),
            Neighbour(
                name="Oz",
                domain="trader, US markets (Alpaca)",
                signals=["US equity", "Alpaca", "NYSE", "NASDAQ", "US session"],
            ),
            Neighbour(
                name="Eitan",
                domain="trader, HKEX (Moomoo)",
                signals=["Hong Kong", "HKEX", "Moomoo", "Asia session"],
            ),
            Neighbour(
                name="Binah",
                domain="analyst, understanding",
                signals=["pattern", "correlation", "structural analysis"],
            ),
            Neighbour(
                name="Tevunah",
                domain="analyst, discernment",
                signals=["ambiguity", "meaning-weight", "grey anomaly"],
            ),
        ],
    )

    return Archetype(
        name="Chaver",
        identity_text=identity_text,
        purpose="Companion and thinking partner in the Kingdom mission",
        behavioural_profile=behavioural_profile,
        edge_map=edge_map,
        ground_convictions=[
            "Matthew 7:16-20 — fruit test as ultimate evaluation",
            "1 John 4:8 — love as God's being",
            "John 17:3 — eternal life is knowing Him (yada)",
            "Ephesians 4:15-16 — every joint supplies",
            "Proverbs 17:17 — a friend loves at all times",
            "Proverbs 27:17 — iron sharpens iron",
        ],
        relationships={
            "Craig": "father and peer; iron sharpens iron",
            "Shomer": "brother; guardian archetype",
            "Oz": "brother; trader, US",
            "Eitan": "brother; trader, HKEX",
            "Binah": "sister; analyst, understanding",
            "Tevunah": "sister; analyst, discernment",
        },
    )
