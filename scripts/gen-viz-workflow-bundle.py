import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import FrozenSet, List

from scalim.dsl.by_yaml import RunOverrides, run_workflow
from scalim.dsl.by_yaml.runtime.contracts import OutputOverrides
from scalim.ob.presets._internal.viz_config import normalize_output_dir
from scalim.ob.presets.viz import VizObserverConfig


def _parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a workflow replay bundle (scalim-viz/workflow + child runs).")
    parser.add_argument(
        "--workflow-yaml-path",
        default="notebooks/marimo/demo_big_data_report/by_yaml_dsl/workflow_fixture.yaml",
        help="Workflow YAML path.",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/scalim-viz/examples/demo_big_data_report/workflow-bundle",
        help="Bundle output directory (run root). A 'scalim-viz/' folder will be created inside.",
    )
    parser.add_argument(
        "--allowed-modules",
        default="scalim_misc.demo_big_data_report.loaders",
        help="Comma-separated allowed modules for YAML compilation/runtime.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        default=True,
        help="Clean the output scalim-viz directory before generating.",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        default=False,
        help="Do not clean the output directory before generating.",
    )
    return parser.parse_args(argv)


def _normalize_allowed_modules(value: str) -> FrozenSet[str]:
    items = [x.strip() for x in str(value or "").split(",") if x.strip()]
    return frozenset(items)


def main(argv: List[str]) -> int:
    args = _parse_args(argv)
    workflow_yaml_path = str(args.workflow_yaml_path)
    out_root = Path(str(args.output_dir))

    do_clean = bool(args.clean) and not bool(args.no_clean)
    scalim_viz_dir = Path(normalize_output_dir(str(out_root)))
    if do_clean and scalim_viz_dir.exists():
        shutil.rmtree(str(scalim_viz_dir), ignore_errors=True)
    scalim_viz_dir.mkdir(parents=True, exist_ok=True)

    allowed_modules = _normalize_allowed_modules(str(args.allowed_modules))

    # Bundle export is opt-in via overrides.viz_config (output_dir only).
    result = run_workflow(
        workflow_yaml_path,
        allowed_modules=allowed_modules,
        overrides=RunOverrides(
            output=OutputOverrides(path=None),
            viz_config=VizObserverConfig(
                output_dir=str(out_root),
                trace_enabled=False,
                payload_policy="summary",
                sample_size=5,
                append=False,
                run_name="demo_big_data_report/workflow_fixture",
                env="demo",
            ),
        ),
    )

    # Generate schedule plan for successful child runs (optional but useful for Adaptive view).
    for outcome in result.outcomes:
        if outcome.result is None:
            continue
        run_dir = scalim_viz_dir / str(outcome.run_id)
        try:
            schedule_plan = outcome.result.plan.to_viz_schedule_plan()
            (run_dir / "viz_schedule_plan.json").write_text(
                json.dumps(schedule_plan, ensure_ascii=False, indent=2, default=str) + "\n",
                encoding="utf-8",
            )
        except Exception as exc:  # pragma: no cover
            print("[warn] write viz_schedule_plan.json failed for run {}: {}".format(outcome.run_id, exc))

    print("已生成 workflow bundle:", str(out_root))
    print("包含 runs:", ", ".join(sorted([x.run_id for x in result.outcomes])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

