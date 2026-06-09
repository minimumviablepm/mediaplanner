"""CPM benchmark lookup from a bundled public-data compilation.

Methodology: there is no free, authoritative CPM API (Guideline/SMI,
Standard Media Index, and eMarketer benchmarks are paid products). This
tool serves a curated table compiled from publicly reported figures,
adjusted for demo, geography tier, and quarter seasonality. Every result
carries data_vintage and a confidence label so the agent can disclose the
benchmark's provenance — and user ratecards always override it.
"""

from __future__ import annotations

import json
import re
from importlib import resources

_DATA = json.loads(
    resources.files("mediaplanner.data").joinpath("cpm_benchmarks.json").read_text()
)

VALID_BUYING_TYPES = ("upfront", "scatter", "programmatic_guaranteed", "open_market")


def _demo_multiplier(demo: str) -> float:
    d = demo.strip().lower().replace(" ", "")
    for key, mult in _DATA["demo_multipliers"].items():
        if key != "default" and key in d:
            return mult
    return _DATA["demo_multipliers"]["default"]


def _geo_multiplier(geography: str) -> tuple[float, str]:
    g = geography.strip().lower()
    if g in ("national", "us", "usa", "united states", "total us"):
        return _DATA["geo_multipliers"]["national"], "national"
    for dma in _DATA["tier1_dmas"]:
        if dma in g:
            return _DATA["geo_multipliers"]["dma_tier1"], "dma_tier1"
    if "dma" in g:
        return _DATA["geo_multipliers"]["dma_tier2"], "dma_tier2"
    return _DATA["geo_multipliers"]["state"], "state"


def _quarter(flight_quarter: str) -> str:
    m = re.search(r"q([1-4])", flight_quarter.strip().lower())
    if not m:
        raise ValueError(
            f"flight_quarter must contain Q1-Q4 (e.g. 'Q3 2026'), got {flight_quarter!r}"
        )
    return f"Q{m.group(1)}"


def cpm_lookup(
    channel: str,
    demo: str,
    geography: str,
    buying_type: str,
    flight_quarter: str,
) -> dict:
    channel = channel.strip().lower()
    buying_type = buying_type.strip().lower()
    if channel not in _DATA["base_cpm_median"]:
        raise ValueError(f"channel must be one of {sorted(_DATA['base_cpm_median'])}")
    if buying_type not in VALID_BUYING_TYPES:
        raise ValueError(f"buying_type must be one of {VALID_BUYING_TYPES}")

    base = _DATA["base_cpm_median"][channel][buying_type]
    demo_mult = _demo_multiplier(demo)
    geo_mult, geo_tier = _geo_multiplier(geography)
    quarter = _quarter(flight_quarter)
    q_mult = _DATA["quarter_multipliers"][quarter]

    median = base * demo_mult * geo_mult * q_mult
    p25 = median * _DATA["spread"]["p25_factor"]
    p75 = median * _DATA["spread"]["p75_factor"]

    # Confidence: medium for national benchmarks, low for sub-national
    # (public reporting is thinnest at DMA level) and for open_market
    # linear (rarely transacted that way).
    confidence = "medium"
    if geo_tier != "national":
        confidence = "low"
    if channel == "linear" and buying_type == "open_market":
        confidence = "low"

    return {
        "channel": channel,
        "demo": demo,
        "geography": geography,
        "geo_tier_applied": geo_tier,
        "buying_type": buying_type,
        "flight_quarter": quarter,
        "cpm_p25": round(p25, 2),
        "cpm_median": round(median, 2),
        "cpm_p75": round(p75, 2),
        "confidence": confidence,
        "data_vintage": _DATA["data_vintage"],
        "source": "Bundled compilation of publicly reported CPM benchmarks; not a live ratecard",
    }
