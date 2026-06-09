"""Cross-channel universe overlap defaults from census/open data.

When the user has no panel (MRI/GfK/single-source) duplication data, the
agent needs a `universe_overlap_pct` input for the deduplication model.
This tool derives defaults from open sources:

- ACS S2801 (computer/internet subscription) for connected-device
  penetration among TV households
- Nielsen "The Gauge" monthly reports (publicly published) for the
  coexistence of linear and streaming viewing in TV homes
- Pew Research Center (2024) for YouTube usage (~83% of US adults)

These are national, household-leaning figures. The output is labeled
"modeled (open-source derived)" so the agent reports the source class
required by Section 4 of the prompt.
"""

from __future__ import annotations

_PAIR_DEFAULTS = {
    # % of the total universe addressable by BOTH channels.
    frozenset(("linear", "ctv")): {
        "overlap_pct": 60.0,
        "basis": (
            "Nielsen Gauge: streaming-capable (CTV) devices present in the "
            "large majority of pay-TV homes; ACS S2801 broadband subscription "
            "~90% of HHs intersected with ~70% CTV penetration"
        ),
    },
    frozenset(("linear", "youtube")): {
        "overlap_pct": 70.0,
        "basis": (
            "Pew Research 2024: ~83% of US adults use YouTube, intersected "
            "with ~80% linear-reachable persons"
        ),
    },
    frozenset(("ctv", "youtube")): {
        "overlap_pct": 80.0,
        "basis": (
            "YouTube is itself the largest CTV app (Nielsen Gauge); CTV "
            "households overwhelmingly include YouTube users"
        ),
    },
}


def universe_overlap(channel_a: str, channel_b: str, measurement_type: str = "persons") -> dict:
    a, b = channel_a.strip().lower(), channel_b.strip().lower()
    pair = frozenset((a, b))
    if pair not in _PAIR_DEFAULTS:
        raise ValueError(
            f"No overlap default for pair ({channel_a}, {channel_b}); "
            "supported channels: linear, ctv, youtube"
        )
    entry = _PAIR_DEFAULTS[pair]
    overlap = entry["overlap_pct"]
    # HH-level overlap runs higher than person-level (co-viewing pools
    # device access at the household).
    if measurement_type.strip().lower() == "households":
        overlap = min(overlap * 1.10, 95.0)

    return {
        "channel_a": a,
        "channel_b": b,
        "measurement_type": measurement_type,
        "universe_overlap_pct": round(overlap, 1),
        "source_class": "modeled (open-source derived)",
        "basis": entry["basis"],
        "note": (
            "National default derived from census/open panel data. If the user "
            "has MRI/GfK or single-source panel duplication data, prefer it and "
            "label the source as 'panel'."
        ),
    }
