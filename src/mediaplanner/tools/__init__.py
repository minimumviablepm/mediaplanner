"""Quantitative planning tools.

Each module implements one tool from the agent prompt on top of an
established, published methodology — these capabilities have no canonical
open-source package, so the implementations cite their methods and data
sources explicitly:

- reach_frequency:  Gamma-Poisson / Negative Binomial (NBD) exposure model
                    (Goodhardt, Ehrenberg & Chatfield), the standard model
                    for TV reach curves.
- deduplication:    Sainsbury random-duplication formula adjusted for
                    universe overlap.
- mmm_priors:       Elasticity priors from published meta-analyses
                    (Sethuraman, Tellis & Briesch 2011) and Google
                    Meridian's documented defaults.
- cpm_lookup:       Bundled benchmark table compiled from publicly
                    reported CPM data, labeled with vintage + confidence.
- universe:         U.S. Census Bureau ACS API (live) with a bundled
                    ACS 2023 snapshot fallback; Nielsen public DMA HH
                    estimates for DMA-level requests.
- overlap:          Cross-channel universe overlap defaults derived from
                    Census/ACS subscription data and published Nielsen
                    Gauge / Pew Research figures.
"""

from mediaplanner.tools.reach_frequency import reach_frequency_model
from mediaplanner.tools.deduplication import deduplication_model
from mediaplanner.tools.mmm_priors import mmm_priors
from mediaplanner.tools.cpm_lookup import cpm_lookup
from mediaplanner.tools.universe import universe_lookup
from mediaplanner.tools.overlap import universe_overlap
from mediaplanner.tools.ratecard import read_ratecard_file

__all__ = [
    "reach_frequency_model",
    "deduplication_model",
    "mmm_priors",
    "cpm_lookup",
    "universe_lookup",
    "universe_overlap",
    "read_ratecard_file",
]
