import argparse
import cProfile
import time
from pathlib import Path
from typing import Iterable, List, Sequence


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Profile/benchmark Scalim execution hotspots via demo_big_data_report SSOT scenario.")
    parser.add_argument("--scale", default="stress", help="demo_big_data_report scale (default: stress)")
    parser.add_argument("--targets", default="relations", help="target set id (default: relations)")
    parser.add_argument("--batch-size", type=int, default=100, help="engine batch_size (default: 100)")
    parser.add_argument("--row-limit", type=int, default=0, help="optional limit of main rows (0 means no limit)")
    parser.add_argument(
        "--profile",
        choices=["none", "cprofile", "memray"],
        default="none",
        help="profiling mode (default: none). For py-spy, use `just profile-cpu`.",
    )
    parser.add_argument(
        "--output-dir",
        default=".tmp/artifacts/perf",
        help="output directory for profiler artifacts (default: .tmp/artifacts/perf)",
    )
    parser.add_argument("--repeat", type=int, default=1, help="repeat runs when profile=none (default: 1)")
    return parser.parse_args()


def _make_discard_row_sink():  # type: ignore[no-untyped-def]
    # 延迟导入: 避免在使用脚本内剖析（`cProfile`/`memray`）时,把导入阶段噪声计入剖析区间。
    from scalim.sinks import IRowSink  # noqa: PLC0415

    class _DiscardRowSink(IRowSink):
        def write_row(self, _row) -> None:  # type: ignore[no-untyped-def]
            return

        def close(self) -> None:
            return

    return _DiscardRowSink()


def _discard_row_sink() -> object:
    # 小缓存: 避免在内层循环中重复分配 `sink` 对象。
    if not hasattr(_discard_row_sink, "_cached"):
        _discard_row_sink._cached = _make_discard_row_sink()  # type: ignore[attr-defined]
    return _discard_row_sink._cached  # type: ignore[attr-defined]


def _resolve_targets(targets_id: str) -> List[str]:
    from scalim_misc.demo_big_data_report.shared import build_target_sets  # noqa: PLC0415

    target_sets = build_target_sets()
    key = str(targets_id or "").strip()
    alias = {
        "relations": "relations_only",
        "derived": "derived_only",
    }.get(key, key)
    if alias not in target_sets:
        msg = "Unknown targets={!r}. Known: {}".format(key, ", ".join(sorted(target_sets)))
        raise KeyError(msg)
    return list(target_sets[alias])


def _prepare_main_rows(scale: str, *, row_limit: int) -> List[object]:
    from scalim_misc.demo_big_data_report.loaders import ECommerceConfig, load_orders, set_config  # noqa: PLC0415

    config = ECommerceConfig.from_scale(scale)
    set_config(config)

    rows: List[object] = load_orders()
    if row_limit > 0:
        rows = rows[: int(row_limit)]
    return rows


def _prepare_engine(scale: str, *, batch_size: int, targets: Sequence[str]):  # type: ignore[no-untyped-def]
    from scalim.execution.engine import ScalimEngine  # noqa: PLC0415
    from scalim.planning import PlanBuilder  # noqa: PLC0415
    from scalim_misc.demo_big_data_report.loaders import ECommerceConfig  # noqa: PLC0415
    from scalim_misc.demo_big_data_report.shared import build_ecommerce_model, build_ecommerce_runtime_bindings  # noqa: PLC0415

    config = ECommerceConfig.from_scale(scale)
    demand = build_ecommerce_model(config=config)
    runtime_bindings = build_ecommerce_runtime_bindings()
    plan = PlanBuilder(demand).build(targets=list(targets))
    return ScalimEngine(
        demand=demand,
        plan=plan,
        runtime_bindings=runtime_bindings,
        batch_size=int(batch_size),
    )


def _run(engine, *, main_rows: Iterable[object]) -> None:  # type: ignore[no-untyped-def]
    # 使用丢弃型流式 `sink`: 避免把结果缓冲到内存列表带来噪声。
    engine.run(main_rows=main_rows, sink=_discard_row_sink())


def main() -> None:
    args = _parse_args()
    targets = _resolve_targets(str(args.targets))

    output_dir = Path(str(args.output_dir))
    output_dir.mkdir(parents=True, exist_ok=True)

    main_rows = _prepare_main_rows(str(args.scale), row_limit=int(args.row_limit))
    engine = _prepare_engine(str(args.scale), batch_size=int(args.batch_size), targets=targets)

    profile = str(args.profile)
    basename = "ecommerce_{}_{}".format(str(args.targets), str(args.scale))

    if profile == "cprofile":
        out = output_dir / "{}.prof".format(basename)
        prof = cProfile.Profile()
        prof.enable()
        _run(engine, main_rows=main_rows)
        prof.disable()
        prof.dump_stats(str(out))
        print("写入:", out)
        return

    if profile == "memray":
        out = output_dir / "{}.bin".format(basename)
        try:
            import memray  # type: ignore[import-not-found]
        except Exception as exc:  # noqa: BLE001
            msg = "memray unavailable (dev-only). Install dev deps then retry. Error: {}".format(exc)
            raise RuntimeError(msg)
        with memray.Tracker(
            str(out),
            file_format=memray.FileFormat.ALL_ALLOCATIONS,
            trace_python_allocators=True,
        ):
            _run(engine, main_rows=main_rows)
        print("写入:", out)
        return

    # `profile == "none"`: 仅做纯计时运行
    repeat = max(1, int(args.repeat))
    start = time.perf_counter()
    for _ in range(repeat):
        _run(engine, main_rows=main_rows)
    dur = time.perf_counter() - start
    print("运行次数:", repeat)
    print("耗时(秒):", round(dur, 6))


if __name__ == "__main__":
    main()
