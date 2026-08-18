"""c30 证据: `lookup_chunk_size` 分片 串行 vs opt-in 并行 A/B(模拟 RTT).

用法（仓库根目录）:
    PYTHONPATH=src python docs/doc/releases/repro/chunk-parallel/run_ab.py
    PYTHONPATH=src python docs/doc/releases/repro/chunk-parallel/run_ab.py --keys 20000 --chunk-size 100 --rtt-ms 5 --max-workers 8

说明:
- 已随仓库提交(`docs/doc/releases/repro/chunk-parallel/`),供用户自行复现.
- 默认用**独立子进程**分别跑 serial / parallel,避免同进程 `ru_maxrss` 高水位被先跑臂污染.
- loader 用 `time.sleep` 模拟固定 RTT;加速比反映「等待重叠」上限,不代表真实数据库表现.
- 结果写入运行目录下 `.tmp/evidence/c30-chunk-parallel/ab_multiprocess.json`(可用 `--out` 覆盖;可再生、不入库).
- 脚本保持 Python 3.6 可跑(与 `src/scalim/` 运行时边界一致).
"""

from __future__ import absolute_import, print_function

import argparse
import json
import multiprocessing as mp
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from scalim.execution.chunk_parallelism import LookupChunkParallelismPolicy
from scalim.execution.context import BatchContext
from scalim.execution.executor.operators.load_ref.executor import LoadRefOperatorExecutor
from scalim.execution.executor.runtime.runtime import ExecutionRuntime
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.hooks import HookManager
from scalim.ob.manager import ObserverManager
from scalim.planning.operators import LoadRefOperatorIr, OperatorType
from scalim.planning.plan import ExecutionPlan
from scalim.spec.ir import FieldIr, KeyIr, LookupStepIr, MainSourceIr, RuntimeHandleIdIr, SourceIr
from scalim.spec.ir.binding import BindingIr, LoaderIr

try:
    import resource
except ImportError:  # pragma: no cover - Windows
    resource = None  # type: ignore[assignment]

_DEFAULT_OUT = Path(".tmp/evidence/c30-chunk-parallel/ab_multiprocess.json")


def _peak_rss_kb() -> Optional[int]:
    if resource is None:
        return None
    # Linux: KB; macOS: bytes — 本证据脚本在 Linux 上采集.
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


def _build(
    *,
    keys: int,
    chunk_size: int,
    rtt_s: float,
    parallel_mode: str,
    parallelize_lookup_chunks: bool,
    max_workers: int,
    max_chunk_workers: Optional[int],
) -> Tuple[ExecutionRuntime, LoadRefOperatorIr, BatchContext, List[int], Dict[str, Any]]:
    stats: Dict[str, Any] = {"calls": 0, "inflight": 0, "max_inflight": 0}
    lock = threading.Lock()
    runtime_bindings = RuntimeBindings()

    def _loader(ids: List[int]) -> Dict[int, Dict[str, Any]]:
        with lock:
            stats["calls"] += 1
            stats["inflight"] += 1
            stats["max_inflight"] = max(stats["max_inflight"], stats["inflight"])
        try:
            time.sleep(rtt_s)
        finally:
            with lock:
                stats["inflight"] -= 1
        return {key: {"name": "Name{}".format(key)} for key in ids}

    def _params_builder(ctx: Any) -> Tuple[Tuple[Any, ...], Dict[str, Any]]:
        return (), {"ids": list(ctx.lookup_keys_list or [])}

    runtime_bindings.source_loaders["targets"] = _loader
    runtime_bindings.params_builders[("targets", "target_id")] = _params_builder
    runtime_bindings.main_source_loaders["orders"] = lambda: []

    source = SourceIr(
        source_id="targets",
        key=KeyIr(key="target_id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr("source_loader:targets")),
        lookup_chunk_size=chunk_size,
    )
    binding = BindingIr(
        key_field="target_id",
        params_builder_ref=RuntimeHandleIdIr("params_builder:targets:target_id"),
    )
    field_spec = FieldIr(field_id="target_name", name="Target", source_id=source.source_id, data_key="name")
    operator = LoadRefOperatorIr(
        operator_id="load_ref",
        operator_type=OperatorType.LOAD_REF.value,
        source_id="targets",
        field_key="target_name",
        lookup_steps=(LookupStepIr(from_field="fk_id", to_source_id=source.source_id, bind=binding),),
    )
    plan = ExecutionPlan(field_specs={"target_name": field_spec}, operators=(operator,))
    runtime = ExecutionRuntime(
        plan=plan,
        hook_manager=HookManager(),
        observer_manager=ObserverManager(),
        main_source=MainSourceIr(source_id="orders", loader_ref=RuntimeHandleIdIr("main_source:orders")),
        sources={"targets": source},
        runtime_bindings=runtime_bindings,
        parallel_mode=parallel_mode,  # type: ignore[arg-type]
        max_workers=max_workers,
        chunk_parallelism=LookupChunkParallelismPolicy(
            parallelize_lookup_chunks=parallelize_lookup_chunks,
            max_chunk_workers=max_chunk_workers,
        ),
    )

    context = BatchContext()
    row_ids = list(range(1, keys + 1))
    for row_id in row_ids:
        context.set_field_value("fk_id", row_id, row_id)
    return runtime, operator, context, row_ids, stats


def _run_once(**kwargs: Any) -> Dict[str, Any]:
    runtime, operator, context, row_ids, stats = _build(**kwargs)
    started = time.perf_counter()
    LoadRefOperatorExecutor().execute(operator, context, row_ids, runtime)
    duration = time.perf_counter() - started
    # 只校验首尾若干值,避免大 shape 下跨进程传完整 values dict.
    sample_ids = [row_ids[0], row_ids[len(row_ids) // 2], row_ids[-1]]
    values_sample = {row_id: context.get_field_value("target_name", row_id) for row_id in sample_ids}
    return {
        "duration_s": duration,
        "calls": int(stats["calls"]),
        "max_inflight": int(stats["max_inflight"]),
        "peak_rss_kb": _peak_rss_kb(),
        "values_sample": values_sample,
        "n_keys": len(row_ids),
        "pid": os.getpid(),
    }


def _worker(kwargs: Dict[str, Any], queue: "mp.Queue[Dict[str, Any]]") -> None:
    try:
        queue.put({"ok": True, "result": _run_once(**kwargs)})
    except Exception as exc:  # pragma: no cover - evidence script
        queue.put({"ok": False, "error": "{}: {}".format(type(exc).__name__, exc)})


def _run_in_subprocess(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    ctx = mp.get_context("spawn")
    queue: "mp.Queue[Dict[str, Any]]" = ctx.Queue()
    proc = ctx.Process(target=_worker, args=(kwargs, queue))
    proc.start()
    payload = queue.get()
    proc.join()
    if proc.exitcode not in (0, None):
        raise RuntimeError("child exited with code {}".format(proc.exitcode))
    if not payload.get("ok"):
        raise RuntimeError(payload.get("error") or "child failed")
    return payload["result"]


def main() -> None:
    parser = argparse.ArgumentParser(description="chunk parallelism A/B (multiprocess RSS)")
    parser.add_argument("--keys", type=int, default=20000, help="unique lookup keys (default: 20000)")
    parser.add_argument("--chunk-size", type=int, default=100)
    parser.add_argument("--rtt-ms", type=float, default=5.0)
    parser.add_argument("--max-workers", type=int, default=8)
    parser.add_argument("--max-chunk-workers", type=int, default=0)
    parser.add_argument("--in-process", action="store_true", help="same-process A/B (RSS not comparable)")
    parser.add_argument("--out", type=Path, default=_DEFAULT_OUT)
    args = parser.parse_args()

    max_chunk_workers = int(args.max_chunk_workers) or None
    common = {
        "keys": int(args.keys),
        "chunk_size": int(args.chunk_size),
        "rtt_s": float(args.rtt_ms) / 1000.0,
        "max_workers": int(args.max_workers),
        "max_chunk_workers": max_chunk_workers,
    }
    n_chunks = (int(args.keys) + int(args.chunk_size) - 1) // int(args.chunk_size)

    run = _run_once if args.in_process else _run_in_subprocess
    serial = run(dict(parallel_mode="seq", parallelize_lookup_chunks=True, **common))
    parallel = run(dict(parallel_mode="adaptive", parallelize_lookup_chunks=True, **common))

    assert serial["values_sample"] == parallel["values_sample"], "merge sample mismatch: parallel != serial"
    assert serial["calls"] == parallel["calls"], "loader call count mismatch"
    assert serial["calls"] == n_chunks, "unexpected chunk call count"

    speedup = serial["duration_s"] / parallel["duration_s"] if parallel["duration_s"] > 0 else float("inf")
    rss_delta_pct = None
    if serial.get("peak_rss_kb") and parallel.get("peak_rss_kb"):
        rss_delta_pct = (parallel["peak_rss_kb"] - serial["peak_rss_kb"]) / float(serial["peak_rss_kb"]) * 100.0

    report = {
        "shape": {
            "keys": int(args.keys),
            "chunk_size": int(args.chunk_size),
            "n_chunks": n_chunks,
            "rtt_ms": float(args.rtt_ms),
            "max_workers": int(args.max_workers),
            "max_chunk_workers": max_chunk_workers,
            "multiprocess": not bool(args.in_process),
        },
        "serial": {k: v for k, v in serial.items() if k != "values_sample"},
        "parallel": {k: v for k, v in parallel.items() if k != "values_sample"},
        "speedup": speedup,
        "values_sample_equal": True,
        "calls_equal": True,
        "peak_rss_delta_pct": rss_delta_pct,
        "gates": {
            "speedup_ge_1_5": speedup >= 1.5,
            "rss_delta_le_10_pct": rss_delta_pct is None or rss_delta_pct <= 10.0,
        },
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(
        "keys={} chunk_size={} n_chunks={} rtt_ms={} max_workers={} max_chunk_workers={} multiprocess={}".format(
            args.keys,
            args.chunk_size,
            n_chunks,
            args.rtt_ms,
            args.max_workers,
            max_chunk_workers,
            not args.in_process,
        )
    )
    print(
        "serial   : {:.3f}s calls={} max_inflight={} peak_rss_kb={} pid={}".format(
            serial["duration_s"],
            serial["calls"],
            serial["max_inflight"],
            serial.get("peak_rss_kb"),
            serial.get("pid"),
        )
    )
    print(
        "parallel : {:.3f}s calls={} max_inflight={} peak_rss_kb={} pid={}".format(
            parallel["duration_s"],
            parallel["calls"],
            parallel["max_inflight"],
            parallel.get("peak_rss_kb"),
            parallel.get("pid"),
        )
    )
    print("speedup  : {:.2f}x (values_sample equal = True)".format(speedup))
    if rss_delta_pct is not None:
        print(
            "peak rss : serial={}KB parallel={}KB delta={:+.2f}%".format(
                serial["peak_rss_kb"],
                parallel["peak_rss_kb"],
                rss_delta_pct,
            )
        )
    print("wrote    : {}".format(out_path))


if __name__ == "__main__":
    main()
