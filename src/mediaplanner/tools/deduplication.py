"""Cross-channel deduplication: Sainsbury formula with overlap adjustment.

Methodology: the Sainsbury (random duplication) model is the standard
industry approach when single-source panel duplication data is not
available. Duplication between two channels is assumed random *within the
overlapping portion of their universes*:

    duplicated  = reach_a * reach_b * universe_overlap
    unduplicated = reach_a + reach_b - duplicated

`universe_overlap_pct` should come from panel/MRI/GfK data when the user
has it; otherwise use `universe_overlap()` (census / open-source derived
defaults) and label the source accordingly.
"""

from __future__ import annotations


def deduplication_model(
    channel_a: str,
    channel_b: str,
    reach_a_pct: float,
    reach_b_pct: float,
    universe_overlap_pct: float,
) -> dict:
    """Combine two channel reaches into unduplicated reach.

    Args:
        reach_a_pct / reach_b_pct: Each channel's reach as % of the SAME
            total universe.
        universe_overlap_pct: % of the universe addressable by both
            channels (panel-sourced if available, otherwise from
            universe_overlap()).
    """
    for name, value in (
        ("reach_a_pct", reach_a_pct),
        ("reach_b_pct", reach_b_pct),
        ("universe_overlap_pct", universe_overlap_pct),
    ):
        if not 0 <= value <= 100:
            raise ValueError(f"{name} must be between 0 and 100, got {value}")

    ra = reach_a_pct / 100.0
    rb = reach_b_pct / 100.0
    overlap_universe = universe_overlap_pct / 100.0

    duplicated = ra * rb * overlap_universe
    unduplicated = ra + rb - duplicated
    # Cannot exceed 100% of universe.
    unduplicated = min(unduplicated, 1.0)

    return {
        "channel_a": channel_a,
        "channel_b": channel_b,
        "unduplicated_reach_pct": round(unduplicated * 100.0, 2),
        "overlap_pct": round(duplicated * 100.0, 2),
        "incremental_reach_from_b": round((unduplicated - ra) * 100.0, 2),
        "model": "Sainsbury random-duplication formula, overlap-adjusted",
    }
