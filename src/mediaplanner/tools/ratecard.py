"""Ratecard file ingestion (Section 2 of the agent prompt).

Reads a user-supplied CSV ratecard from disk and returns raw rows for the
agent to normalize and validate. Parsing only — the agent performs the
coverage check, anomaly flags, and session_ratecard locking in
conversation, where the user can confirm anomalies.
"""

from __future__ import annotations

import csv
from pathlib import Path

MAX_ROWS = 500


def read_ratecard_file(path: str) -> dict:
    p = Path(path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"Ratecard file not found: {path}")
    if p.suffix.lower() not in (".csv", ".txt"):
        raise ValueError(
            "Only CSV ratecards are supported by this reader. For XLSX, ask "
            "the user to export to CSV."
        )

    with p.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = []
        for i, row in enumerate(reader):
            if i >= MAX_ROWS:
                break
            rows.append({(k or "").strip(): (v or "").strip() for k, v in row.items()})

    return {
        "path": str(p),
        "columns": reader.fieldnames or [],
        "row_count": len(rows),
        "truncated": len(rows) >= MAX_ROWS,
        "rows": rows,
    }
