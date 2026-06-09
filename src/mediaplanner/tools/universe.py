"""Universe estimates from the U.S. Census Bureau (ACS).

Methodology: the Census Bureau's ACS is the canonical free, official
source for population and household universes. This tool attempts a live
call to api.census.gov (ACS 5-year, no API key required at low volume)
and falls back to a bundled ACS 2023 snapshot when offline. Demo
qualifiers (age range, gender) are applied via national age/sex fractions
from the same snapshot — a stated assumption when applied sub-nationally.

DMA-level universes are NOT a census geography; the top-10 DMA TV-HH
estimates bundled here come from publicly reported Nielsen figures and
are labeled low confidence.
"""

from __future__ import annotations

import json
import re
import urllib.request
from importlib import resources

_DATA = json.loads(
    resources.files("mediaplanner.data").joinpath("acs_universe_2023.json").read_text()
)

_CENSUS_URL = (
    "https://api.census.gov/data/2023/acs/acs5?get=B01003_001E,B11001_001E&for={geo}"
)
_TIMEOUT_S = 8


def _live_census_totals(geography_key: str) -> tuple[float, float] | None:
    """Return (population_000s, households_000s) from api.census.gov, or None."""
    if geography_key == "national":
        geo = "us:1"
    else:
        return None  # state FIPS mapping handled via snapshot for simplicity
    try:
        with urllib.request.urlopen(
            _CENSUS_URL.format(geo=geo), timeout=_TIMEOUT_S
        ) as resp:
            rows = json.loads(resp.read().decode())
        pop, hh = float(rows[1][0]), float(rows[1][1])
        return pop / 1000.0, hh / 1000.0
    except Exception:
        return None


def _age_fraction(demo: str) -> tuple[float, str]:
    d = demo.strip().lower().replace(" ", "")
    fractions = _DATA["age_fractions_of_total_population"]
    for key, frac in sorted(fractions.items(), key=lambda kv: -len(kv[0])):
        if key in d:
            return frac, key
    return fractions["18+"], "18+ (default — no age range matched)"


def _gender_fraction(demo: str) -> tuple[float, str]:
    d = demo.strip().lower()
    if re.match(r"^\s*(m|men|male)", d):
        return _DATA["gender_fraction"]["m"], "male"
    if re.match(r"^\s*(w|f|women|female)", d):
        return _DATA["gender_fraction"]["w"], "female"
    return 1.0, "all persons"


def universe_lookup(demo: str, geography: str, measurement_type: str) -> dict:
    measurement_type = measurement_type.strip().lower()
    if measurement_type not in ("persons", "households"):
        raise ValueError("measurement_type must be 'persons' or 'households'")

    g = geography.strip().lower()
    confidence_note = None

    # Resolve base geography totals.
    if g in ("national", "us", "usa", "united states", "total us"):
        live = _live_census_totals("national")
        if live:
            pop_000s, hh_000s = live
            source = "U.S. Census Bureau ACS 5-year via api.census.gov (live)"
            vintage = "ACS 2023 5-year (live API)"
        else:
            pop_000s = _DATA["national"]["population_000s"]
            hh_000s = _DATA["national"]["households_000s"]
            source = "U.S. Census Bureau ACS 2023 5-year (bundled snapshot; live API unreachable)"
            vintage = _DATA["vintage"]
    elif g in _DATA["state_population_000s"]:
        pop_000s = _DATA["state_population_000s"][g]
        hh_000s = pop_000s / _DATA["national"]["avg_household_size"]
        source = "U.S. Census Bureau ACS 2023 5-year (bundled snapshot, state level)"
        vintage = _DATA["vintage"]
        confidence_note = "State households estimated via national avg household size"
    else:
        # Try DMA match.
        for dma, hh in _DATA["dma_tv_households_000s"].items():
            if dma.split("-")[0] in g or g in dma:
                pop_000s = hh * _DATA["national"]["avg_household_size"]
                hh_000s = hh
                source = "Nielsen DMA TV-household estimates as publicly reported (bundled)"
                vintage = _DATA["vintage"]
                confidence_note = (
                    "DMA is not a census geography; figure is a publicly reported "
                    "Nielsen estimate — LOW confidence. Persons derived via avg HH size."
                )
                break
        else:
            raise ValueError(
                f"Unresolvable geography {geography!r}: supported are 'national', "
                "US state names, or top-10 DMA names. Per the fallback hierarchy, "
                "report this field as unresolvable rather than substituting a value."
            )

    if measurement_type == "households":
        universe_000s = hh_000s
        demo_note = "Household universes are not demo-filtered (demo applies to persons)"
    else:
        age_frac, age_label = _age_fraction(demo)
        gender_frac, gender_label = _gender_fraction(demo)
        universe_000s = pop_000s * age_frac * gender_frac
        demo_note = (
            f"Applied national age fraction for '{age_label}' and gender "
            f"'{gender_label}' to the geography total (stated assumption)"
        )

    return {
        "demo": demo,
        "geography": geography,
        "measurement_type": measurement_type,
        "universe_000s": round(universe_000s, 1),
        "source": source,
        "vintage": vintage,
        "notes": "; ".join(n for n in (demo_note, confidence_note) if n),
    }
