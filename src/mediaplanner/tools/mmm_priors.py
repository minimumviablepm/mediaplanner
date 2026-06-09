"""MMM elasticity/saturation priors from published meta-analyses.

Methodology: there is no open-source service that returns category-level
MMM priors, so this tool encodes the most widely cited public evidence
base — Sethuraman, Tellis & Briesch (2011) advertising-elasticity
meta-analysis and Google Meridian's documented prior guidance — as a
curated table with category and KPI adjustments. Every response carries
its source and a confidence label; the agent must surface "low"
confidence before interpreting results.
"""

from __future__ import annotations

import json
from importlib import resources

_DATA = json.loads(
    resources.files("mediaplanner.data").joinpath("mmm_priors.json").read_text()
)


def _match_category(advertiser_category: str) -> tuple[str, float]:
    cat = advertiser_category.strip().lower()
    multipliers = _DATA["category_multipliers"]
    for key, mult in multipliers.items():
        if key != "default" and key in cat:
            return key, mult
    return "default", multipliers["default"]


def mmm_priors(advertiser_category: str, channel: str, kpi: str) -> dict:
    channel = channel.strip().lower()
    base = _DATA["channel_base"].get(channel)
    if base is None:
        raise ValueError(
            f"channel must be one of {sorted(_DATA['channel_base'])}, got {channel!r}"
        )

    matched_category, cat_mult = _match_category(advertiser_category)
    kpi_key = kpi.strip().lower()
    kpi_adj = _DATA["kpi_adjustments"].get(
        kpi_key, {"elasticity_multiplier": 1.0, "lag_delta_weeks": 0}
    )

    confidence = base["confidence"]
    # Unmatched category or unmapped KPI weakens the prior.
    if matched_category == "default" or kpi_key not in _DATA["kpi_adjustments"]:
        confidence = "low"

    elasticity = base["elasticity"] * cat_mult * kpi_adj["elasticity_multiplier"]
    return {
        "advertiser_category": advertiser_category,
        "matched_category": matched_category,
        "channel": channel,
        "kpi": kpi,
        "elasticity_estimate": round(elasticity, 4),
        "saturation_point_index": base["saturation_point_index"],
        "lag_effect_weeks": base["lag_effect_weeks"] + kpi_adj["lag_delta_weeks"],
        "prior_confidence": confidence,
        "source": (
            "Sethuraman, Tellis & Briesch (2011) JMR meta-analysis; "
            "Google Meridian documented prior guidance; "
            "category/KPI adjustments are stated planning priors"
        ),
    }
