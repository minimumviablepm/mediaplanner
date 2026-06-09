"""Interactive cross-channel media planning agent.

Runs the system prompt in media-planning-agent-prompt.md against the
Anthropic API with the five planning model tools (plus the overlap and
ratecard helpers) wired in as real, locally executed tools.

Usage:
    export ANTHROPIC_API_KEY=...
    python -m mediaplanner.agent
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import anthropic

from mediaplanner import tools

MODEL = os.environ.get("MEDIAPLANNER_MODEL", "claude-opus-4-8")
MAX_TOKENS = 16000

SYSTEM_SUFFIX = """

---

## Tool availability note (runtime)

All five model tools are AVAILABLE in this session, plus two helpers:

- `universe_overlap(channel_a, channel_b, measurement_type)` — returns a
  `universe_overlap_pct` derived from census/open-source data when the user
  has no panel duplication data. Label its output as
  "modeled (open-source derived)" in Section 4.
- `read_ratecard_file(path)` — reads a user-supplied CSV ratecard from a
  local path so you can execute Section 2.

`reach_frequency_model` REQUIRES `cpm_override` — always pass the
session_ratecard CPM or a `cpm_lookup` median. Tool errors are returned to
you as error results; surface them to the user rather than retrying with
fabricated inputs.
"""


def _load_system_prompt() -> str:
    override = os.environ.get("MEDIAPLANNER_PROMPT")
    candidates = [Path(override)] if override else []
    here = Path(__file__).resolve()
    candidates += [
        here.parents[2] / "media-planning-agent-prompt.md",  # repo layout
        Path.cwd() / "media-planning-agent-prompt.md",
    ]
    for c in candidates:
        if c and c.exists():
            return c.read_text() + SYSTEM_SUFFIX
    raise FileNotFoundError(
        "media-planning-agent-prompt.md not found; set MEDIAPLANNER_PROMPT"
    )


TOOL_DEFINITIONS = [
    {
        "name": "reach_frequency_model",
        "description": (
            "Gamma-Poisson/NBD reach model for one channel. Returns gross "
            "impressions, reach %, avg frequency, marginal reach curve, and a "
            "95% CI. cpm_override is REQUIRED (session_ratecard or cpm_lookup "
            "median). Call once per channel after budgets and CPMs are set."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "channel": {"type": "string", "enum": ["linear", "ctv", "youtube"]},
                "budget": {"type": "number", "description": "Channel budget, USD"},
                "demo": {"type": "string"},
                "geography": {"type": "string"},
                "flight_weeks": {"type": "integer"},
                "universe_size": {
                    "type": "number",
                    "description": "Universe in thousands (from universe_lookup)",
                },
                "cpm_override": {
                    "type": "number",
                    "description": "Net CPM USD — session_ratecard or cpm_lookup median",
                },
            },
            "required": [
                "channel", "budget", "demo", "geography",
                "flight_weeks", "universe_size", "cpm_override",
            ],
        },
    },
    {
        "name": "deduplication_model",
        "description": (
            "Sainsbury overlap-adjusted deduplication for a channel pair. "
            "Both reaches must be % of the SAME universe. Get "
            "universe_overlap_pct from panel data or the universe_overlap tool."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "channel_a": {"type": "string"},
                "channel_b": {"type": "string"},
                "reach_a_pct": {"type": "number"},
                "reach_b_pct": {"type": "number"},
                "universe_overlap_pct": {"type": "number"},
            },
            "required": [
                "channel_a", "channel_b", "reach_a_pct",
                "reach_b_pct", "universe_overlap_pct",
            ],
        },
    },
    {
        "name": "mmm_priors",
        "description": (
            "Category/channel/KPI elasticity and saturation priors from "
            "published meta-analyses. Surface prior_confidence='low' to the "
            "user before interpreting."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "advertiser_category": {"type": "string"},
                "channel": {"type": "string", "enum": ["linear", "ctv", "youtube"]},
                "kpi": {"type": "string"},
            },
            "required": ["advertiser_category", "channel", "kpi"],
        },
    },
    {
        "name": "cpm_lookup",
        "description": (
            "Benchmark CPM (p25/median/p75) from a bundled public-data "
            "compilation. Do NOT call for cells covered by a validated "
            "session_ratecard. Always report data_vintage and confidence."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "channel": {"type": "string", "enum": ["linear", "ctv", "youtube"]},
                "demo": {"type": "string"},
                "geography": {"type": "string"},
                "buying_type": {
                    "type": "string",
                    "enum": ["upfront", "scatter", "programmatic_guaranteed", "open_market"],
                },
                "flight_quarter": {"type": "string", "description": "e.g. 'Q3 2026'"},
            },
            "required": ["channel", "demo", "geography", "buying_type", "flight_quarter"],
        },
    },
    {
        "name": "universe_lookup",
        "description": (
            "Universe size (thousands) from US Census ACS (live API with "
            "bundled snapshot fallback). Supports national, US states, and "
            "top-10 DMAs (DMA = low confidence Nielsen public estimate). "
            "Raises for unresolvable geographies — report those as "
            "unresolvable per the fallback hierarchy."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "demo": {"type": "string"},
                "geography": {"type": "string"},
                "measurement_type": {"type": "string", "enum": ["persons", "households"]},
            },
            "required": ["demo", "geography", "measurement_type"],
        },
    },
    {
        "name": "universe_overlap",
        "description": (
            "Census/open-source-derived universe_overlap_pct for a channel "
            "pair, for use in deduplication_model when no panel data exists. "
            "Source class is 'modeled (open-source derived)'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "channel_a": {"type": "string", "enum": ["linear", "ctv", "youtube"]},
                "channel_b": {"type": "string", "enum": ["linear", "ctv", "youtube"]},
                "measurement_type": {"type": "string", "enum": ["persons", "households"]},
            },
            "required": ["channel_a", "channel_b"],
        },
    },
    {
        "name": "read_ratecard_file",
        "description": (
            "Read a user-supplied CSV ratecard from a local file path and "
            "return raw rows for Section 2 normalization and validation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
]

DISPATCH = {
    "reach_frequency_model": tools.reach_frequency_model,
    "deduplication_model": tools.deduplication_model,
    "mmm_priors": tools.mmm_priors,
    "cpm_lookup": tools.cpm_lookup,
    "universe_lookup": tools.universe_lookup,
    "universe_overlap": tools.universe_overlap,
    "read_ratecard_file": tools.read_ratecard_file,
}


def _execute_tool(name: str, tool_input: dict) -> tuple[str, bool]:
    try:
        result = DISPATCH[name](**tool_input)
        return json.dumps(result), False
    except Exception as exc:  # surface tool failures to the model, don't crash
        return f"Error: {type(exc).__name__}: {exc}", True


def run_turn(client: anthropic.Anthropic, system: list, messages: list) -> None:
    """Run one user turn through the agentic loop, printing output."""
    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            thinking={"type": "adaptive"},
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        for block in response.content:
            if block.type == "text":
                print(block.text)

        if response.stop_reason != "tool_use":
            return

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                print(f"  [tool] {block.name}({json.dumps(block.input)[:200]})")
                content, is_error = _execute_tool(block.name, dict(block.input))
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": content,
                    "is_error": is_error,
                })
        messages.append({"role": "user", "content": tool_results})


def main() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Set ANTHROPIC_API_KEY to run the agent.")

    client = anthropic.Anthropic()
    system = [{
        "type": "text",
        "text": _load_system_prompt(),
        "cache_control": {"type": "ephemeral"},
    }]
    messages: list = []

    print("Cross-channel media planning agent. Describe your brief "
          "(advertiser, budget, flight dates, KPI, demo, geography). "
          "Ctrl-D or 'quit' to exit.\n")
    while True:
        try:
            user_input = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user_input or user_input.lower() in ("quit", "exit"):
            break
        messages.append({"role": "user", "content": user_input})
        try:
            run_turn(client, system, messages)
        except anthropic.APIError as exc:
            print(f"[api error] {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
