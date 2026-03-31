import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Dict, FrozenSet, List

from scalim.dsl.by_yaml import RunOverrides, run_workflow
from scalim.ob.presets._internal.viz_config import normalize_output_dir
from scalim.ob.presets.viz import VizObserverConfig
from scalim_misc.notebook_support.pathing import demo_big_data_report_workflow_demo_yaml_path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate demo_big_data_report workflow replay bundle + committed baselines.")
    parser.add_argument(
        "--workflow-yaml-ssot",
        default=str(demo_big_data_report_workflow_demo_yaml_path(__file__)),
        help="SSOT workflow YAML (will be copied to <output-dir>/workflow.yaml).",
    )
    parser.add_argument(
        "--output-dir",
        default=".tmp/artifacts/scalim-viz/examples/demo_big_data_report/workflow-bundle-advanced",
        help="Bundle output directory (run root). A 'scalim-viz/' folder will be created inside.",
    )
    parser.add_argument(
        "--manifest-filename",
        default="bundle_manifest.json",
        help="Manifest file name written under <output-dir>/scalim-viz/ for DevTools autoload.",
    )
    parser.add_argument(
        "--allowed-modules",
        default="scalim_misc.demo_big_data_report.loaders,scalim.workflow.loaders",
        help="Comma-separated allowed modules for YAML compilation/runtime.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        default=True,
        help="Clean output directory before generating.",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        default=False,
        help="Do not clean output directory before generating.",
    )
    return parser.parse_args(argv)


def _normalize_allowed_modules(value: str) -> FrozenSet[str]:
    items = [x.strip() for x in str(value or "").split(",") if x.strip()]
    return frozenset(items)


def _to_posix_path(path: Path) -> str:
    return str(path).replace("\\", "/")


def _write_bundle_manifest(
    *,
    scalim_viz_dir: Path,
    manifest_path: Path,
) -> None:
    directory_label = _to_posix_path(scalim_viz_dir.relative_to(REPO_ROOT))
    runs = []
    for child in sorted(scalim_viz_dir.iterdir(), key=lambda p: p.name):
        if not child.is_dir():
            continue
        snapshot = child / "viz_snapshot.json"
        events = child / "viz_events.jsonl"
        schedule = child / "viz_schedule_plan.json"
        if not snapshot.exists() and not events.exists() and not schedule.exists():
            continue
        runs.append(
            {
                "id": str(child.name),
                "path": _to_posix_path(child.relative_to(REPO_ROOT)),
            }
        )

    payload: Dict[str, object] = {
        "version": 1,
        "directoryLabel": directory_label,
        "runs": runs,
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: List[str]) -> int:
    args = _parse_args(argv)
    ssot = Path(str(args.workflow_yaml_ssot)).expanduser().resolve(strict=False)
    if not ssot.exists():
        print("[错误] 缺少工作流 YAML SSOT: {}".format(str(ssot)), file=sys.stderr)
        return 2

    out_root = Path(str(args.output_dir)).expanduser().resolve(strict=False)
    do_clean = bool(args.clean) and not bool(args.no_clean)

    out_root.mkdir(parents=True, exist_ok=True)
    scalim_viz_dir = Path(normalize_output_dir(str(out_root)))

    if do_clean:
        if scalim_viz_dir.exists():
            shutil.rmtree(str(scalim_viz_dir), ignore_errors=True)
        for filename in ("workflow.yaml", "detail.csv", "metrics.csv", "report.xlsx"):
            try:
                (out_root / filename).unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass

    scalim_viz_dir.mkdir(parents=True, exist_ok=True)

    workflow_yaml_path = out_root / "workflow.yaml"
    workflow_yaml_path.write_text(ssot.read_text(encoding="utf-8"), encoding="utf-8")
    for demand_filename in (
        "workflow_demo_big_data_report_detail_demand.yaml",
        "workflow_demo_big_data_report_metrics_demand.yaml",
    ):
        (out_root / demand_filename).write_text((ssot.parent / demand_filename).read_text(encoding="utf-8"), encoding="utf-8")

    allowed_modules = _normalize_allowed_modules(str(args.allowed_modules))

    result = run_workflow(
        str(workflow_yaml_path),
        allowed_modules=allowed_modules,
        init_vars={"order_ids": []},
        path_aliases={"@": str(REPO_ROOT)},
        overrides=RunOverrides(
            viz_config=VizObserverConfig(
                output_dir=str(out_root),
                trace_enabled=False,
                payload_policy="summary",
                sample_size=5,
                append=False,
                run_name="demo_big_data_report/workflow_demo_big_data_report",
                env="demo",
            ),
        ),
    )

    # 对成功的子运行补写 `viz_schedule_plan.json`(可选;用于可视化计划视角).
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
        except Exception as exc:
            print(
                "警告: 写入 `viz_schedule_plan.json` 失败(run_id={}): {}".format(outcome.run_id, exc),
                file=sys.stderr,
            )

    manifest_path = scalim_viz_dir / str(args.manifest_filename)
    _write_bundle_manifest(scalim_viz_dir=scalim_viz_dir, manifest_path=manifest_path)

    print("已生成工作流演示包:", _to_posix_path(out_root))
    print("包清单:", _to_posix_path(manifest_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
