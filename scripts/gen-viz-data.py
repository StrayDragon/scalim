import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from scalim.dsl.by_yaml.runtime.contracts import OutputOverrides, RunOverrides
from scalim.dsl.by_yaml.runtime.entrypoints import run
from scalim.ob.presets.viz import VizObserverConfig


def _ensure_repo_root_on_syspath() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


DEMO_OUTPUT_FIELDS_ADAPTIVE_PARALLEL2 = [
    "order_id",
    "order_date",
    "quantity",
    "unit_price",
    "discount_rate",
    "customer_name",
    "customer_phone",
    "registration_date",
    "customer_level",
    "product_name",
    "product_brand",
    "product_cost",
    "product_category_id",
    "category_name",
    "warehouse_name",
    "region_name_value",
    "region_name_display",
    "region_manager",
    "promotion_name",
    "promotion_discount",
    "no_promotion",
    "payment_method_name",
    "logistics_name",
    "logistics_speed",
    "price_adjustment",
    "shipping_fee",
    "tax_rate",
    "order_amount",
    "profit",
    "tax_amount",
    "final_price",
]


def _parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Scalim Viz artifacts from YAML DSL demo.")
    parser.add_argument(
        "--yaml-path",
        default="notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml",
        help="YAML DSL path for the demo run.",
    )
    parser.add_argument(
        "--mode",
        choices=("events-only", "events+trace"),
        default="events-only",
        help=("Viz artifact profile. events-only -> viz_events.jsonl only; events+trace -> viz_events.jsonl + viz_trace.jsonl."),
    )
    parser.add_argument(
        "--payload-policy",
        default=None,
        help="Payload policy (summary/sample/full/none). Defaults to summary for events-only, full for events+trace.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory for viz artifacts.",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=5,
        help="Sample size for payload_policy=sample.",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=0,
        help="Max workers hint for parallel_mode=adaptive (0 means auto).",
    )
    parser.add_argument(
        "--scenarios",
        default="seq",
        help=(
            "Comma-separated run scenarios. Supported: seq, adaptive, adaptive_parallel2. Example: --scenarios adaptive,adaptive_parallel2"
        ),
    )
    parser.add_argument(
        "--compact-loader-calls",
        action="store_true",
        default=None,
        help=("Compact repeated loader_called events in the output JSONL. Defaults to enabled when mode=events-only."),
    )
    parser.add_argument(
        "--no-compact-loader-calls",
        action="store_true",
        default=None,
        help="Disable compaction of loader_called events (keeps every loader_called line).",
    )
    return parser.parse_args(argv)


def _resolve_profile_root(mode: str) -> Tuple[str, Path]:
    profile = "events+trace" if mode == "events+trace" else "events-only"
    root = Path("artifacts/scalim-viz/examples/demo_big_data_report") / profile / "scalim-viz"
    return profile, root


def _resolve_run_dir(mode: str, scenario: str) -> str:
    base = "run_demo_big_data_trace" if mode == "events+trace" else "run_demo_big_data_events"
    if scenario == "seq":
        return base
    if scenario == "adaptive":
        return "{}_adaptive".format(base)
    if scenario == "adaptive_parallel2":
        return "{}_adaptive_parallel2".format(base)
    raise ValueError("未知场景: {}".format(scenario))


def _normalize_scenarios(raw: str) -> List[str]:
    items = [x.strip() for x in str(raw or "").split(",") if x.strip()]
    if not items:
        return ["seq"]
    return items


def _resolve_payload_policy(value: Optional[str], mode: str) -> str:
    if value:
        return value
    if mode == "events+trace":
        return "full"
    return "summary"


def _compact_loader_calls(events_path: Path) -> None:
    temp_path = events_path.with_suffix(events_path.suffix + ".tmp")
    pending_event: Optional[dict] = None
    pending_sig: Optional[tuple] = None
    pending_count = 0
    pending_duration = 0

    def flush(handle) -> None:
        nonlocal pending_event, pending_sig, pending_count, pending_duration
        if pending_event is None:
            return
        payload = pending_event.get("payload")
        if isinstance(payload, dict) and pending_count > 1:
            payload["merged_calls"] = pending_count
            if "duration_ms" in payload:
                payload["duration_ms_total"] = pending_duration
        handle.write(json.dumps(pending_event, ensure_ascii=False, default=str) + "\n")
        pending_event = None
        pending_sig = None
        pending_count = 0
        pending_duration = 0

    with events_path.open("r", encoding="utf-8") as src, temp_path.open("w", encoding="utf-8") as dst:
        for line in src:
            raw = line.strip()
            if not raw:
                continue
            event = json.loads(raw)
            if event.get("event_type") != "loader_called":
                flush(dst)
                dst.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
                continue
            payload = event.get("payload")
            payload_dict = payload if isinstance(payload, dict) else {}
            signature = (
                event.get("node_ref", {}).get("id"),
                payload_dict.get("cache_status"),
                payload_dict.get("lookup_key_count"),
                tuple(payload_dict.get("field_keys") or []),
                payload_dict.get("result_count"),
            )
            duration_ms = payload_dict.get("duration_ms")
            if pending_event is not None and signature == pending_sig:
                pending_count += 1
                if isinstance(duration_ms, int):
                    pending_duration += duration_ms
                continue
            flush(dst)
            pending_event = event
            pending_sig = signature
            pending_count = 1
            pending_duration = duration_ms if isinstance(duration_ms, int) else 0
        flush(dst)
    temp_path.replace(events_path)


def _output_fields_override_for_scenario(scenario: str) -> Optional[List[str]]:
    if scenario == "adaptive_parallel2":
        return list(DEMO_OUTPUT_FIELDS_ADAPTIVE_PARALLEL2)
    return None


def _parallel_mode_for_scenario(scenario: str) -> str:
    if scenario == "seq":
        return "seq"
    if scenario in ("adaptive", "adaptive_parallel2"):
        return "adaptive"
    raise ValueError("未知场景: {}".format(scenario))


def main(argv: List[str]) -> int:
    _ensure_repo_root_on_syspath()
    args = _parse_args(argv)
    yaml_path = args.yaml_path
    allowed_modules = frozenset(["notebooks.marimo.demo_big_data_report._loaders"])

    scenarios = _normalize_scenarios(args.scenarios)
    trace_enabled = args.mode == "events+trace"
    payload_policy = _resolve_payload_policy(args.payload_policy, args.mode)

    profile, profile_root = _resolve_profile_root(args.mode)
    if args.output_dir:
        output_base = Path(args.output_dir)
    else:
        output_base = profile_root

    multi = len(scenarios) > 1
    outputs: List[Path] = []

    for scenario in scenarios:
        run_dir = _resolve_run_dir(args.mode, scenario)
        output_dir = output_base / run_dir if multi else (output_base if args.output_dir else (profile_root / run_dir))
        output_dir.mkdir(parents=True, exist_ok=True)

        output_fields = _output_fields_override_for_scenario(scenario)
        output_overrides = OutputOverrides(path=None, fields=output_fields) if output_fields is not None else OutputOverrides(path=None)

        viz_config = VizObserverConfig(
            output_path=str(output_dir / "viz_events.jsonl"),
            snapshot_path=str(output_dir / "viz_snapshot.json"),
            trace_enabled=trace_enabled,
            payload_policy=payload_policy,
            sample_size=args.sample_size,
            run_name="demo_big_data_report/{}".format(scenario),
        )

        parallel_mode = _parallel_mode_for_scenario(scenario)
        result = run(
            yaml_path,
            allowed_modules=allowed_modules,
            overrides=RunOverrides(
                output=output_overrides,
                viz_config=viz_config,
            ),
            parallel_mode=parallel_mode,
            max_workers=int(args.max_workers or 0),
            runtime_vars={"order_ids": []},
        )

        try:
            schedule_plan = result.plan.to_viz_schedule_plan()
            with (output_dir / "viz_schedule_plan.json").open("w", encoding="utf-8") as handle:
                json.dump(schedule_plan, handle, ensure_ascii=False, indent=2, default=str)
        except Exception as exc:  # pragma: no cover
            # 计划视角产物是可选项: 不应阻塞现有可视化数据生成流程.
            print("[警告] 写入 `viz_schedule_plan.json` 失败:", exc)

        compact = args.compact_loader_calls
        if args.no_compact_loader_calls:
            compact = False
        if compact is None:
            compact = args.mode == "events-only"
        if compact:
            _compact_loader_calls(output_dir / "viz_events.jsonl")

        outputs.append(output_dir)

    print("可视化档位:", profile)
    for path in outputs:
        print("可视化输出:", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
