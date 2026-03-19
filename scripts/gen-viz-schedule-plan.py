import argparse
import json
import sys
from pathlib import Path
from typing import FrozenSet, List, Optional

from scalim.dsl.by_yaml.runtime.entrypoints import compile as compile_yaml
from scalim.planning.builder import PlanBuilder


def _parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate viz_schedule_plan.json from YAML + run_started.targets in viz_events.jsonl. "
            "If run_started is missing (e.g. workflow-level events), skip without error."
        ),
    )
    parser.add_argument(
        "--yaml-path",
        default="notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml",
        help="YAML DSL path.",
    )
    parser.add_argument(
        "--events-jsonl",
        required=True,
        help="viz_events.jsonl path. Reads run_started.payload.targets from it.",
    )
    parser.add_argument(
        "--allowed-modules",
        default="scalim_misc.demo_big_data_report.loaders",
        help="Comma-separated allowed modules for YAML compilation.",
    )
    parser.add_argument(
        "--output-json",
        required=True,
        help="Output JSON path (typically <run_dir>/viz_schedule_plan.json).",
    )
    return parser.parse_args(argv)


def _read_targets_from_events(events_path: Path) -> Optional[List[str]]:
    for line in events_path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        event = json.loads(raw)
        if event.get("event_type") != "run_started":
            continue
        payload = event.get("payload") or {}
        targets = payload.get("targets") or []
        if not isinstance(targets, list):
            raise ValueError("`run_started.payload.targets` 必须是列表")
        return [str(x) for x in targets]
    return None


def main(argv: List[str]) -> int:
    args = _parse_args(argv)
    yaml_path = str(args.yaml_path)
    events_path = Path(str(args.events_jsonl))
    output_path = Path(str(args.output_json))
    output_path.parent.mkdir(parents=True, exist_ok=True)

    allowed_modules_raw = [x.strip() for x in str(args.allowed_modules or "").split(",") if x.strip()]
    allowed_modules: FrozenSet[str] = frozenset(allowed_modules_raw)

    targets = _read_targets_from_events(events_path)
    if targets is None:
        print(
            "告警: 跳过生成 `viz_schedule_plan.json`: 未在 {} 中找到 `run_started` 事件".format(str(events_path)),
            file=sys.stderr,
        )
        return 0
    compilation = compile_yaml(yaml_path, allowed_modules=allowed_modules)
    plan = PlanBuilder(compilation.demand_ir).build(targets=list(targets))

    schedule_plan = plan.to_viz_schedule_plan()
    output_path.write_text(json.dumps(schedule_plan, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print("已写入:", str(output_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
