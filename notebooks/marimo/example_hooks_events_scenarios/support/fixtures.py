# force-en
"""Minimal demand/workflow YAML fixtures for hook/event scenario demos."""

from __future__ import annotations

from pathlib import Path
from typing import FrozenSet

ALLOWED_MODULES: FrozenSet[str] = frozenset(["scalim_misc.examples.public_api._fixtures"])

LOADER_ITEMS = "scalim_misc.examples.public_api._fixtures:load_items"

# Fixture row count from load_items() — used as sync estimate.  # force-en
SYNC_ESTIMATED_ROWS = 3
# Large enough to trip mock dispatch async threshold (default 100).  # force-en
ASYNC_ESTIMATED_ROWS = 10_000


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_minimal_demand_yaml(path: Path) -> Path:
    # force-en
    """Demand that loads 3 items; outputs are provided via RunOverrides at run time."""
    write_text(
        path,
        """\
name: hooks_events_scenarios_minimal

main_source:
  source_id: items
  loader: "{loader}"
  fields:
    item_id: {{extract: item_id, name: Item ID}}
    dim_id: {{extract: dim_id, name: Dim ID}}

sources: {{}}
""".format(loader=LOADER_ITEMS),
    )
    return path


def write_minimal_workflow_yaml(path: Path, *, demand_rel: str = "demand.yaml") -> Path:
    write_text(
        path,
        """\
workflow:
  runs:
    - id: main
      demand: {demand}
""".format(demand=demand_rel),
    )
    return path
