#!/usr/bin/env python3
"""Generate an HTML report of parsed vs unknown FLP event coverage."""

from __future__ import annotations

import argparse
import html
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def _pct(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return (numerator / denominator) * 100


def _event_id_name(event: Any) -> str:
    name = getattr(event.id, "name", None)
    if name is None:
        return str(int(event.id))
    return str(name)


def _import_pyflp() -> tuple[Any, Any, Any]:
    try:
        import pyflp  # type: ignore
        from pyflp._events import UnknownDataEvent  # type: ignore
        from pyflp.plugin import VSTPluginEvent  # type: ignore
        return pyflp, UnknownDataEvent, VSTPluginEvent
    except ModuleNotFoundError:
        repo_root = Path(__file__).resolve().parents[1]
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))

    try:
        import pyflp  # type: ignore
        from pyflp._events import UnknownDataEvent  # type: ignore
        from pyflp.plugin import VSTPluginEvent  # type: ignore
        return pyflp, UnknownDataEvent, VSTPluginEvent
    except ModuleNotFoundError as exc:
        missing = exc.name or "dependency"
        raise SystemExit(
            "Could not import pyflp runtime dependency "
            f"({missing}).\n"
            "Install project dependencies and rerun, for example:\n"
            "  python3.10 -m venv .venv310\n"
            "  .venv310/bin/pip install -e '.[dev]'\n"
            "  .venv310/bin/python tools/flp_parse_report.py /path/to/file.flp "
            "-o parse-report.html"
        ) from exc


def build_report(flp_path: Path, top_n: int = 25) -> str:
    pyflp, UnknownDataEvent, VSTPluginEvent = _import_pyflp()
    project = pyflp.parse(flp_path)
    events = list(project.events)

    total_events = len(events)
    unknown_top_level = [event for event in events if isinstance(event, UnknownDataEvent)]
    parsed_events = total_events - len(unknown_top_level)

    event_type_counts = Counter(type(event).__name__ for event in events)
    top_level_id_counts = Counter(
        (int(event.id), _event_id_name(event), type(event).__name__) for event in events
    )
    unknown_top_level_id_counts = Counter(int(event.id) for event in unknown_top_level)

    unknown_vst_subevents: list[tuple[int, int]] = []
    for event in events:
        if isinstance(event, VSTPluginEvent):
            for sub_event in event["events"]:
                if type(sub_event["id"]) is int:
                    unknown_vst_subevents.append((sub_event["id"], len(sub_event["data"])))
    unknown_vst_counts = Counter(sub_id for sub_id, _ in unknown_vst_subevents)

    parsed_pct = _pct(parsed_events, total_events)
    unknown_pct = 100.0 - parsed_pct if total_events else 0.0

    type_rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(type_name)}</td>"
        f"<td>{count}</td>"
        "</tr>"
        for type_name, count in event_type_counts.most_common(top_n)
    )
    if not type_rows:
        type_rows = "<tr><td colspan='2'>No events</td></tr>"

    id_rows = "\n".join(
        "<tr>"
        f"<td>{event_id}</td>"
        f"<td>{html.escape(event_name)}</td>"
        f"<td>{html.escape(event_type)}</td>"
        f"<td>{count}</td>"
        "</tr>"
        for (event_id, event_name, event_type), count in top_level_id_counts.most_common(top_n)
    )
    if not id_rows:
        id_rows = "<tr><td colspan='4'>No events</td></tr>"

    unknown_top_level_rows = "\n".join(
        "<tr>"
        f"<td>{event_id}</td>"
        f"<td>{count}</td>"
        "</tr>"
        for event_id, count in unknown_top_level_id_counts.most_common(top_n)
    )
    if not unknown_top_level_rows:
        unknown_top_level_rows = "<tr><td colspan='2'>None</td></tr>"

    unknown_vst_rows = "\n".join(
        "<tr>"
        f"<td>{sub_id}</td>"
        f"<td>{count}</td>"
        "</tr>"
        for sub_id, count in unknown_vst_counts.most_common(top_n)
    )
    if not unknown_vst_rows:
        unknown_vst_rows = "<tr><td colspan='2'>None</td></tr>"

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PyFLP Parse Report</title>
<style>
* {{ box-sizing: border-box; }}
body {{
  margin: 24px;
  font-family: "SF Pro Text", "Segoe UI", sans-serif;
  color: #1f2937;
  background: linear-gradient(180deg, #f7fafc, #eef2f7);
}}
h1, h2 {{ margin-top: 0; }}
.grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}}
.card {{
  background: #ffffff;
  border: 1px solid #dbe3ee;
  border-radius: 12px;
  padding: 14px;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05);
}}
.metric {{ font-size: 28px; font-weight: 700; margin-top: 8px; }}
.ok {{ color: #127d3e; }}
.warn {{ color: #b54708; }}
.bad {{ color: #b42318; }}
.bar {{
  width: 100%;
  height: 16px;
  border-radius: 999px;
  overflow: hidden;
  background: #e5e7eb;
  border: 1px solid #d1d5db;
}}
.bar > div {{
  height: 100%;
  background: linear-gradient(90deg, #16a34a, #4ade80);
}}
table {{
  width: 100%;
  border-collapse: collapse;
  background: #fff;
  border: 1px solid #dbe3ee;
  border-radius: 10px;
  overflow: hidden;
}}
th, td {{ text-align: left; padding: 10px; border-bottom: 1px solid #eef2f7; }}
th {{ background: #f8fafc; font-weight: 600; }}
section {{ margin-bottom: 20px; }}
</style>
</head>
<body>
<h1>PyFLP Parse Coverage Report</h1>
<p><strong>File:</strong> {html.escape(str(flp_path.resolve()))}</p>

<div class="grid">
  <div class="card">
    <div>Total events</div>
    <div class="metric">{total_events}</div>
  </div>
  <div class="card">
    <div>Parsed events</div>
    <div class="metric ok">{parsed_events} ({parsed_pct:.2f}%)</div>
  </div>
  <div class="card">
    <div>Unknown top-level events</div>
    <div class="metric {'bad' if unknown_top_level else 'ok'}">{len(unknown_top_level)} ({unknown_pct:.2f}%)</div>
  </div>
  <div class="card">
    <div>Unknown VST sub-events</div>
    <div class="metric {'warn' if unknown_vst_subevents else 'ok'}">{len(unknown_vst_subevents)}</div>
  </div>
</div>

<section class="card">
  <h2>Top-level Parse Coverage</h2>
  <div class="bar"><div style="width: {parsed_pct:.2f}%"></div></div>
  <p>{parsed_events} of {total_events} top-level events parsed into known event types.</p>
</section>

<section>
  <h2>Top Event Types (Top {top_n})</h2>
  <table>
    <thead><tr><th>Event Type</th><th>Count</th></tr></thead>
    <tbody>{type_rows}</tbody>
  </table>
</section>

<section>
  <h2>Top Event IDs (Top {top_n})</h2>
  <table>
    <thead><tr><th>ID</th><th>Name</th><th>Parsed As</th><th>Count</th></tr></thead>
    <tbody>{id_rows}</tbody>
  </table>
</section>

<section>
  <h2>Unknown Top-level Event IDs (Top {top_n})</h2>
  <table>
    <thead><tr><th>ID</th><th>Count</th></tr></thead>
    <tbody>{unknown_top_level_rows}</tbody>
  </table>
</section>

<section>
  <h2>Unknown VST Sub-event IDs (Top {top_n})</h2>
  <table>
    <thead><tr><th>Sub-event ID</th><th>Count</th></tr></thead>
    <tbody>{unknown_vst_rows}</tbody>
  </table>
</section>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate an HTML report showing parsed vs unknown FLP event coverage."
    )
    parser.add_argument("flp_file", type=Path, help="Path to the .flp file to parse")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("parse-report.html"),
        help="Output HTML file path (default: parse-report.html)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=25,
        help="Number of rows to include in top tables (default: 25)",
    )
    args = parser.parse_args()

    report_html = build_report(args.flp_file, top_n=args.top)
    args.output.write_text(report_html, encoding="utf-8")
    print(f"Report written to: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
