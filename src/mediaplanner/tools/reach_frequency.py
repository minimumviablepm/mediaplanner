"""Reach/frequency model: Gamma-Poisson (Negative Binomial Distribution).

Methodology: the NBD exposure model (Goodhardt, Ehrenberg & Chatfield,
"The Dirichlet: A Comprehensive Model of Buying Behaviour", and decades of
TV audience research) is the standard closed-form model for media reach
curves. Individual exposure counts follow a negative binomial with mean m
(average exposures per addressable person) and dispersion k:

    reach = addressable_fraction * (1 - (1 + m/k) ** -k)

Lower k = more heterogeneous exposure (heavy/light viewer skew), which
flattens the reach curve. Channel parameters below are stated planning
assumptions, not fitted to a proprietary panel — the agent must surface
that in its reasoning blocks.
"""

from __future__ import annotations

import math

# (addressable_fraction_of_universe, dispersion_k)
# addressable fraction sources: Nielsen Gauge / Total Audience public
# reports (linear persons-using-TV penetration), CTV device penetration
# (~70% of HHs, Leichtman Research public releases), Pew Research 2024
# (~83% of US adults use YouTube; discounted for ad-reachable usage).
CHANNEL_PARAMS = {
    "linear": {"addressable_fraction": 0.80, "dispersion_k": 0.35},
    "ctv": {"addressable_fraction": 0.70, "dispersion_k": 0.30},
    "youtube": {"addressable_fraction": 0.85, "dispersion_k": 0.20},
}

# Relative uncertainty applied to k to produce the 95% interval. NBD fits
# to public single-source panel data typically vary by roughly this much
# across markets and dayparts.
K_UNCERTAINTY = 0.30

# Default CPMs used only if no cpm_override is provided AND the caller did
# not run cpm_lookup. The agent prompt forbids that path; this guard makes
# the failure loud instead of silent.
_VALID_CHANNELS = set(CHANNEL_PARAMS)


def _nbd_reach_fraction(mean_exposures: float, k: float) -> float:
    if mean_exposures <= 0:
        return 0.0
    return 1.0 - (1.0 + mean_exposures / k) ** (-k)


def reach_frequency_model(
    channel: str,
    budget: float,
    demo: str,
    geography: str,
    flight_weeks: int,
    universe_size: float,
    cpm_override: float | None = None,
) -> dict:
    """Model gross impressions, reach %, and average frequency.

    Args:
        channel: "linear" | "ctv" | "youtube".
        budget: Working media budget in USD for this channel.
        demo: Target demo string (carried through for labeling).
        geography: Geography string (carried through for labeling).
        flight_weeks: Flight length in weeks (longer flights accumulate
            reach: dispersion is scaled by weeks**0.2 — a stated
            assumption approximating audience turnover).
        universe_size: Target universe in thousands (persons or HHs,
            consistent with the CPM basis).
        cpm_override: Net CPM in USD. REQUIRED in practice — pass the
            session_ratecard CPM or a cpm_lookup result. Raises if absent
            so the agent cannot silently fabricate a CPM.
    """
    if channel not in _VALID_CHANNELS:
        raise ValueError(f"channel must be one of {sorted(_VALID_CHANNELS)}")
    if cpm_override is None or cpm_override <= 0:
        raise ValueError(
            "cpm_override is required: pass the session_ratecard CPM or a "
            "cpm_lookup result. This model does not assume CPMs."
        )
    if budget <= 0 or universe_size <= 0 or flight_weeks <= 0:
        raise ValueError("budget, universe_size, and flight_weeks must be positive")

    params = CHANNEL_PARAMS[channel]
    addressable_frac = params["addressable_fraction"]
    # Longer flights see audience turnover, which behaves like higher k.
    k = params["dispersion_k"] * (flight_weeks ** 0.2)

    universe_persons = universe_size * 1000.0
    addressable_persons = universe_persons * addressable_frac

    gross_impressions = budget / cpm_override * 1000.0
    mean_exposures = gross_impressions / addressable_persons

    def reach_pct_at(k_value: float, m: float) -> float:
        return addressable_frac * _nbd_reach_fraction(m, k_value) * 100.0

    reach_pct = reach_pct_at(k, mean_exposures)
    reached_persons = universe_persons * reach_pct / 100.0
    avg_frequency = gross_impressions / reached_persons if reached_persons else 0.0

    # Marginal reach curve: incremental reach (pts) per +10% spend step.
    marginal_curve = []
    prev = reach_pct_at(k, 0.0)
    for step in range(1, 11):
        spend = budget * step / 10.0
        m = (spend / cpm_override * 1000.0) / addressable_persons
        r = reach_pct_at(k, m)
        marginal_curve.append(
            {"spend_increment": round(spend, 2), "incremental_reach": round(r - prev, 3)}
        )
        prev = r

    # 95% interval from dispersion uncertainty (lower k -> lower reach).
    reach_low = reach_pct_at(k * (1 - K_UNCERTAINTY), mean_exposures)
    reach_high = reach_pct_at(k * (1 + K_UNCERTAINTY), mean_exposures)

    return {
        "channel": channel,
        "demo": demo,
        "geography": geography,
        "gross_impressions": round(gross_impressions, 0),
        "reach_pct": round(reach_pct, 2),
        "avg_frequency": round(avg_frequency, 2),
        "marginal_reach_curve": marginal_curve,
        "confidence_interval_95": {
            "reach_low": round(min(reach_low, reach_high), 2),
            "reach_high": round(max(reach_low, reach_high), 2),
        },
        "model": "Gamma-Poisson/NBD reach model (Goodhardt-Ehrenberg-Chatfield)",
        "assumptions": {
            "addressable_fraction": addressable_frac,
            "dispersion_k_effective": round(k, 4),
            "cpm_used": cpm_override,
            "note": (
                "Channel parameters are stated planning assumptions sourced "
                "from public penetration data, not a fitted proprietary panel."
            ),
        },
    }
