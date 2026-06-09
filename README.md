# mediaplanner

A cross-channel media planning agent (Linear TV / CTV / YouTube) built on the
Anthropic API. The system prompt lives in
[`media-planning-agent-prompt.md`](media-planning-agent-prompt.md); the five
quantitative tools it orchestrates are implemented locally in
[`src/mediaplanner/tools/`](src/mediaplanner/tools/) and executed for real on
every plan — the model never simulates their outputs.

## Quick start

```sh
pip install -e .
export ANTHROPIC_API_KEY=sk-ant-...
mediaplanner            # or: python -m mediaplanner.agent
```

Then describe a brief:

> you> Plan $5M for Acme Outdoor (retail) — flight 2026-09-07 to 2026-11-01,
> primary KPI reach, demo A25-54, national. Ratecard at ./rates.csv

The agent gate-keeps required inputs, ingests/validates the ratecard,
allocates budget, models reach and deduplication, and assesses KPI
achievability — per the eight output sections in the prompt.

## Tools and methodology

There is no canonical open-source package for any of these capabilities
(reach modeling, CPM benchmarks, and dedup panels are proprietary —
Nielsen, Comscore, Guideline). Each tool therefore implements the most
widely regarded *published* methodology on open data, and labels its
provenance in every response:

| Tool | Methodology / data source | Confidence handling |
|---|---|---|
| `reach_frequency_model` | Gamma-Poisson / Negative Binomial (NBD) exposure model (Goodhardt, Ehrenberg & Chatfield) — the textbook standard for TV reach curves. Channel addressability/dispersion parameters are stated planning assumptions from public penetration data. | 95% CI from ±30% dispersion uncertainty |
| `deduplication_model` | Sainsbury random-duplication formula, adjusted so duplication only occurs within the overlapping universe | Inherits the overlap source label |
| `mmm_priors` | Sethuraman, Tellis & Briesch (2011) JMR advertising-elasticity meta-analysis + Google Meridian documented prior guidance, with category/KPI adjustments | `prior_confidence` high/medium/low; unmatched categories degrade to low |
| `cpm_lookup` | Bundled compilation of publicly reported US CPM benchmarks (eMarketer/Guideline/trade-press figures), adjusted for demo, geo tier, and quarter | `data_vintage` + confidence on every result; sub-national = low |
| `universe_lookup` | **Live U.S. Census Bureau ACS API** (`api.census.gov`, free) with a bundled ACS 2023 snapshot fallback; top-10 DMA TV-HH figures from publicly reported Nielsen estimates | Source string says live vs. snapshot; DMA = low confidence |
| `universe_overlap` (helper) | Census/ACS S2801 subscription data, Nielsen "The Gauge" public reports, Pew Research 2024 YouTube usage — used to source `universe_overlap_pct` when the user has no MRI/GfK panel data | Labeled `modeled (open-source derived)`; panel data preferred when available |
| `read_ratecard_file` (helper) | CSV reader so the agent can execute the Section 2 ratecard ingestion/validation flow | Parsing only — anomaly confirmation stays in conversation |

The tools are pure-Python stdlib (no numpy/scipy required) so they run and
test anywhere; only the agent loop needs the `anthropic` package.

## Tests

```sh
python -m unittest discover -s tests -v
```

22 tests cover model math (monotonicity, bounds, CI bracketing, dedup
identities), data-table integrity, and the gate-keeping error paths (e.g.
`reach_frequency_model` refuses to run without a CPM; `universe_lookup`
raises on unresolvable geographies instead of fabricating a value).

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Required |
| `MEDIAPLANNER_MODEL` | `claude-opus-4-8` | Model override |
| `MEDIAPLANNER_PROMPT` | repo prompt file | System prompt path override |

## Known limitations

- Reach-curve parameters are stated assumptions, not fits to a proprietary
  single-source panel — the agent discloses this in its `[reasoning]` blocks.
- CPM benchmarks are a static compilation with a labeled vintage, not a live
  pricing feed.
- `universe_lookup` resolves national, US states, and the top-10 DMAs;
  anything else is reported as unresolvable per the prompt's fallback
  hierarchy.
- XLSX ratecards must be exported to CSV.
