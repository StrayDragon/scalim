#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""外部基线对比 · 扩展证据探针（扫参曲线 / 派生函数复杂度 / 慢源关联分片并行 / Python 3.6 边界）.

配套主矩阵脚本: docs/doc/releases/repro/external-baseline/run_ab.py（形状定义与方法论同源）。
数据资产: docs/doc/assets/data/external-baseline-0.10.probes.json（由本脚本产出）。

探针 1 sweep-rows  行数扫描    宽度固定 20 派生列，rows ∈ [1k..1M]，csv；三侧对照
探针 2 sweep-cols  列数扫描    行数固定 10k，派生列 ∈ [5..600]，csv；三侧对照
探针 3 calc-weight 派生函数复杂度 10k×20，三级函数体（L0 算术 / L1 十次循环 / L2 百次循环）；
                               pandas/polars 的重函数用惯用逃生门：apply(axis=1) / map_elements
探针 4 relation-rtt 慢源关联分片并行 keys 模式（一次整表键集），RTT ∈ {5,20,50}ms，
                               配置：全量单次 / 分片串行 / 分片并行 W=4（两种分片大小）
探针 5 py36-boundary Python 3.6 最低兼容边界（docker python:3.6 容器，scalim-only，
                               引擎路径零三方依赖；与 3.10 同 shape 同 golden 口径）

测量口径与主矩阵一致：子进程隔离墙钟 + VmHWM 真实峰值常驻内存；
golden = run0 全表读回校验（行数 + 派生列校验和）。

运行（仓库根目录；--runs >= 3 为正式证据）：
    just bench-external-probes                 # 全部探针（约 20-30 分钟）
    uv run python docs/doc/releases/repro/external-baseline/run_probes.py --runs 3
    uv run python docs/doc/releases/repro/external-baseline/run_probes.py --runs 1 --scale 0.05  # 冒烟

输出: <repo>/.tmp/evidence/external-baseline/probes/result.json (rebuildable; not committed)
诚实边界: 薄/规整合成函数；RTT 为 sleep 模拟（真实远端源的网络抖动/连接池另计）；
单机单环境；数字不可跨机迁移。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple


REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
_cur = REPO_ROOT
while _cur != os.path.dirname(_cur):
    if os.path.isfile(os.path.join(_cur, "pyproject.toml")) and os.path.isdir(os.path.join(_cur, "src")):
        REPO_ROOT = _cur
        break
    _cur = os.path.dirname(_cur)

SWEEP_ROW_POINTS = [1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000, 500000, 1000000]
SWEEP_COL_POINTS = [5, 10, 25, 50, 100, 200, 400, 600]
SWEEP_BASE_ROWS = 10000
SWEEP_BASE_FLAT = 20
CALC_ROWS = 10000
CALC_FLAT = 20
RTT_KEYS = 20000
RTT_CHUNKS = [100, 250]
RTT_POINTS_MS = [5, 20, 50]
PY36_SHAPES = [
    {"id": "P_S2_csv_50k", "rows": 50000, "n_flat": 100, "sink": "csv", "batch_size": 1000},
    {"id": "P_S4_long_500k", "rows": 500000, "n_flat": 4, "sink": "csv", "batch_size": 1000},
    {"id": "P_S7_relation_30k", "rows": 30000, "n_flat": 0, "sink": "csv", "batch_size": 500, "relation": True,
     "side_rows": 5000},
]
BASE_FIELDS = ("id", "v0", "v1")
SAMPLE_ROWS = 50
RELATION_SIDE_ROWS = 5000


def scaled(rows: int, scale: float) -> int:
    return max(1000, int(rows * scale))


def source_row(i: int) -> Dict[str, Any]:
    return {"id": i, "v0": float(i % 97), "v1": float(i % 13)}


def side_row(sid: int) -> Dict[str, Any]:
    return {"sid": sid, "s0": (sid % 17) * 1.5, "s1": (sid % 29) * 0.5}


def out_fields(n_flat: int, relation: bool = False) -> List[str]:
    fields = list(BASE_FIELDS) + ["d{}".format(j) for j in range(n_flat)]
    if relation:
        fields += ["fk", "s0", "s1", "r0", "r1"]
    return fields


# --- 派生函数复杂度分级（L0 算术 / L1 十次循环 / L2 百次循环）---
def calc_level(level: int, v0: float, v1: float, j: int) -> float:
    if level == 0:
        return (v0 + v1) if j % 3 == 0 else ((v0 - v1) if j % 3 == 1 else (v0 * v1))
    acc = int(v0) + j
    n = 10 if level == 1 else 100
    for _ in range(n):
        acc = (acc * 31 + 7) & 0xFFFF
    return float(acc) + v1


def checksum_targets(n_flat: int, relation: bool) -> List[str]:
    targets: List[str] = []
    if n_flat:
        targets += ["d0"] + (["d1"] if n_flat > 1 else [])
    if relation:
        targets += ["r0", "r1"]
    return targets


def expected_checksums(rows: int, n_flat: int, relation: bool, level: int = 0,
                       only_first_n: int = -1) -> Dict[str, float]:
    targets = checksum_targets(n_flat, relation)
    sums: Dict[str, float] = {name: 0.0 for name in targets}
    limit = rows if only_first_n < 0 else min(rows, only_first_n)
    for i in range(limit):
        v0, v1 = float(i % 97), float(i % 13)
        if "d0" in sums:
            sums["d0"] += calc_level(level, v0, v1, 0)
        if "d1" in sums:
            sums["d1"] += calc_level(level, v0, v1, 1)
        if relation and i < rows:
            s = side_row(i % RELATION_SIDE_ROWS)
            if "r0" in sums:
                sums["r0"] += v0 + s["s0"]
            if "r1" in sums:
                sums["r1"] += v1 * s["s1"]
    return sums


def checksum_close(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))


# ---------------------------------------------------------------------------
# 三侧实现（扫参 / 复杂度探针共用）
# ---------------------------------------------------------------------------
def _calc_for_level(level: int, j: int):
    def _calc(v0: float, v1: float) -> float:
        return calc_level(level, v0, v1, j)

    return _calc


def probe_run_pandas(shape: Dict[str, Any], out_path: str) -> Dict[str, Any]:
    import pandas as pd

    rows, n_flat, level = shape["rows"], shape["n_flat"], shape.get("calc_level", 0)
    t0 = time.perf_counter()
    df = pd.DataFrame(source_row(i) for i in range(rows))
    if level == 0:
        v0, v1 = df["v0"].to_numpy(), df["v1"].to_numpy()
        for j in range(n_flat):
            df["d{}".format(j)] = (v0 + v1) if j % 3 == 0 else ((v0 - v1) if j % 3 == 1 else (v0 * v1))
    else:
        # 惯用逃生门：逻辑不可向量化时用 apply 逐行执行 Python 函数（单次 pass 产出全部派生列）
        cols = [(_calc_for_level(level, j), "d{}".format(j)) for j in range(n_flat)]

        def _apply_row(row):
            return pd.Series([f(row["v0"], row["v1"]) for f, _ in cols])

        derived = df.apply(_apply_row, axis=1)
        derived.columns = [name for _, name in cols]
        df = pd.concat([df, derived], axis=1)
    df = df[out_fields(n_flat)]
    df.to_csv(out_path, header=True, index=False)
    return {"total_s": time.perf_counter() - t0}


def probe_run_polars(shape: Dict[str, Any], out_path: str) -> Dict[str, Any]:
    import polars as pl

    rows, n_flat, level = shape["rows"], shape["n_flat"], shape.get("calc_level", 0)
    t0 = time.perf_counter()
    df = pl.from_dicts([source_row(i) for i in range(rows)],
                       schema={"id": pl.Int64, "v0": pl.Float64, "v1": pl.Float64})
    if level == 0:
        exprs = []
        for j in range(n_flat):
            if j % 3 == 0:
                exprs.append((pl.col("v0") + pl.col("v1")).alias("d{}".format(j)))
            elif j % 3 == 1:
                exprs.append((pl.col("v0") - pl.col("v1")).alias("d{}".format(j)))
            else:
                exprs.append((pl.col("v0") * pl.col("v1")).alias("d{}".format(j)))
        df = df.with_columns(exprs)
    else:
        # 惯用逃生门：逻辑不可向量化时用 map_elements 逐行执行 Python 函数（单次 pass 产出全部派生列）
        def _row_map(row):
            return [calc_level(level, row["v0"], row["v1"], j) for j in range(n_flat)]

        derived = df.select(
            pl.struct(["v0", "v1"]).map_elements(_row_map, return_dtype=pl.List(pl.Float64)).alias("_d")
        )
        df = df.hstack(pl.DataFrame(derived["_d"].to_list(), schema=["d{}".format(j) for j in range(n_flat)]))
    df = df.select(out_fields(n_flat))
    df.write_csv(out_path, include_header=True)
    return {"total_s": time.perf_counter() - t0}


def probe_run_scalim(shape: Dict[str, Any], out_path: str) -> Dict[str, Any]:
    from scalim.execution.engine import ScalimEngine
    from scalim.execution.runtime_bindings import RuntimeBindings
    from scalim.planning import PlanBuilder
    from scalim.sinks import CSVSink
    from scalim.spec.ir import (
        CallBySpecIr,
        CallByValueIr,
        DemandIr,
        DerivedFieldIr,
        FieldIr,
        MainSourceIr,
        RuntimeHandleIdIr,
    )

    rows, n_flat, level = shape["rows"], shape["n_flat"], shape.get("calc_level", 0)
    batch_size = shape.get("batch_size", 500)
    main = MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.loader"))
    field_irs: List[Any] = [
        FieldIr(field_id="id", name="id", source_id=main.source_id),
        FieldIr(field_id="v0", name="v0", source_id=main.source_id),
        FieldIr(field_id="v1", name="v1", source_id=main.source_id),
    ]
    calculators: Dict[str, Any] = {}
    for j in range(n_flat):
        fid = "d{}".format(j)
        calculators[fid] = _calc_for_level(level, j)
        field_irs.append(
            DerivedFieldIr(
                field_id=fid, name=fid, dependencies=("v0", "v1"),
                call_by=CallBySpecIr(
                    reference=RuntimeHandleIdIr(handle_id=fid + ".calc"),
                    kwargs=(
                        ("v0", CallByValueIr(kind="field", value="v0")),
                        ("v1", CallByValueIr(kind="field", value="v1")),
                    ),
                    field_names=("v0", "v1"),
                ),
            )
        )
    demand = DemandIr.from_irs(sources=[], fields=tuple(field_irs), main_source=main, name="probe")
    plan = PlanBuilder(demand).build()
    fields = out_fields(n_flat)
    sink = CSVSink(out_path, field_names=fields, header_names=fields)
    t0 = time.perf_counter()
    engine = ScalimEngine(
        demand=demand, plan=plan,
        runtime_bindings=RuntimeBindings(main_source_loaders={}, derived_calculators=calculators),
        batch_size=batch_size, parallel_mode="seq",
    )
    engine.run(main_rows=(source_row(i) for i in range(rows)), sink=sink)
    return {"total_s": time.perf_counter() - t0}


# ---------------------------------------------------------------------------
# S7 关联（供 py36 边界复用；sqlite 真实 IO）
# ---------------------------------------------------------------------------
def ensure_sqlite_fixture(db_path: str, main_rows: int) -> None:
    import sqlite3

    if os.path.exists(db_path):
        return
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("CREATE TABLE main_rows (id INTEGER PRIMARY KEY, fk INTEGER, v0 REAL, v1 REAL)")
        cur.execute("CREATE TABLE side_rows (sid INTEGER PRIMARY KEY, s0 REAL, s1 REAL)")
        cur.executemany("INSERT INTO main_rows VALUES (?,?,?,?)",
                        [(i, i % RELATION_SIDE_ROWS, float(i % 97), float(i % 13)) for i in range(main_rows)])
        cur.executemany("INSERT INTO side_rows VALUES (?,?,?)",
                        [(sid, (sid % 17) * 1.5, (sid % 29) * 0.5) for sid in range(RELATION_SIDE_ROWS)])
        conn.commit()
    finally:
        conn.close()


def run_relation_rtt(config: Dict[str, Any]) -> Dict[str, Any]:
    """keys 模式慢源关联：整表键集一次 lookup，分片 + opt-in 片间并行（sleep 模拟单次往返 RTT）.

    方法论对齐 docs/doc/releases/repro/chunk-parallel/run_ab.py（0.10.0 证据）。
    """
    import threading

    from scalim.execution.engine import ScalimEngine
    from scalim.execution.pipeline.overrides import PipelineOverrides
    from scalim.execution.runtime_bindings import RuntimeBindings
    from scalim.planning import PlanBuilder
    from scalim.sinks import CSVSink
    from scalim.spec.ir import (
        BindingIr,
        DemandIr,
        FieldIr,
        KeyIr,
        LoaderIr,
        MainSourceIr,
        RuntimeHandleIdIr,
        SourceIr,
    )

    keys = int(config["keys"])
    chunk_size = config.get("chunk_size")
    rtt_s = float(config["rtt_s"])
    parallel = bool(config.get("parallel"))
    max_workers = int(config.get("max_workers", 4))
    out_path = config["_out_path"]

    stats = {"calls": 0, "inflight": 0, "max_inflight": 0}
    lock = threading.Lock()

    def _side_loader(sids=None):  # type: ignore[no-unused-argument]
        key_list = sorted(set(sids or ()))
        with lock:
            stats["calls"] += 1
            stats["inflight"] += 1
            stats["max_inflight"] = max(stats["max_inflight"], stats["inflight"])
        try:
            time.sleep(rtt_s)
        finally:
            with lock:
                stats["inflight"] -= 1
        return {k: {"sid": k, "s0": (k % 17) * 1.5} for k in key_list}

    def _side_params(ctx):  # type: ignore[no-untyped-def]
        return (), {"sids": list(ctx.lookup_keys_list or [])}

    main = MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.loader"))
    side_loader_ir = LoaderIr(
        callable_ref=RuntimeHandleIdIr(handle_id="side.loader"),
        bindings={"sid": BindingIr(key_field="sid", params_builder_ref=RuntimeHandleIdIr("side.sid.params_builder"))},
    )
    side_source = SourceIr(
        source_id="side", key=KeyIr(key="sid"), loader_spec=side_loader_ir,
        lookup_chunk_size=chunk_size,
    )
    relation = main["fk"].join(side_source["sid"])
    field_irs: List[Any] = [
        FieldIr(field_id="fk", name="fk", source_id=main.source_id),
        FieldIr(field_id="s0", name="s0", source_id=side_source.source_id, data_key="s0", relation=relation),
    ]
    demand = DemandIr.from_irs(sources=[side_source], fields=tuple(field_irs), main_source=main, name="rtt")
    plan = PlanBuilder(demand).build()
    fields = ["fk", "s0"]
    sink = CSVSink(out_path, field_names=fields, header_names=fields)

    overrides = None
    if parallel:
        overrides = PipelineOverrides(parallelize_lookup_chunks=True, max_chunk_workers=max_workers)

    engine = ScalimEngine(
        demand=demand, plan=plan,
        runtime_bindings=RuntimeBindings(
            main_source_loaders={}, derived_calculators={},
            source_loaders={"side": _side_loader},
            params_builders={("side", "sid"): _side_params},
        ),
        batch_size=keys,  # 单批装下全部行：等价 keys 模式整表键集一次 lookup
        parallel_mode="adaptive" if parallel else "seq",
        max_workers=max_workers,
        pipeline_overrides=overrides,
    )

    def _main_rows():
        for i in range(1, keys + 1):
            yield {"fk": i}

    t0 = time.perf_counter()
    engine.run(main_rows=_main_rows(), sink=sink)
    elapsed = time.perf_counter() - t0
    if os.path.exists(out_path):
        os.remove(out_path)
    return {"total_s": elapsed, "calls": stats["calls"], "max_inflight": stats["max_inflight"]}


# ---------------------------------------------------------------------------
# golden 校验
# ---------------------------------------------------------------------------
def verify(shape: Dict[str, Any], out_path: str, full: bool = True) -> Dict[str, Any]:
    import csv

    rows = shape["rows"]
    targets = checksum_targets(shape["n_flat"], bool(shape.get("relation")))
    level = shape.get("calc_level", 0)
    sums = {name: 0.0 for name in targets}
    count = 0
    with open(out_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            count += 1
            if full or count <= SAMPLE_ROWS:
                for name in targets:
                    sums[name] += float(row[name])
    expected = expected_checksums(rows, shape["n_flat"], bool(shape.get("relation")), level) if full else \
        expected_checksums(rows, shape["n_flat"], bool(shape.get("relation")), level, only_first_n=SAMPLE_ROWS)
    ok = count == rows and all(checksum_close(sums[k], expected[k]) for k in targets)
    return {"golden_ok": ok, "rows_read": count}


# ---------------------------------------------------------------------------
# worker（子进程隔离）
# ---------------------------------------------------------------------------
def _rss_now_kb() -> int:
    with open("/proc/self/statm") as f:
        return int(int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 1024)


def _hwm_kb() -> int:
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith("VmHWM:"):
                return int(line.split()[1])
    return 0


def worker(task: Dict[str, Any]) -> int:
    kind = task["kind"]
    out_path = task["out_path"]
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    before = _rss_now_kb()
    skipped = None
    body: Dict[str, Any] = {}
    try:
        if kind == "sweep" or kind == "calc":
            side = task["side"]
            if side == "pandas":
                body = probe_run_pandas(task["shape"], out_path)
            elif side == "polars":
                body = probe_run_polars(task["shape"], out_path)
            else:
                body = probe_run_scalim(task["shape"], out_path)
        elif kind == "relation":
            body = run_relation_rtt(task["config"])
        else:
            raise ValueError("unknown kind " + kind)
    except ImportError as exc:
        skipped = "import: {}".format(exc)
    if kind == "relation":
        # RTT 探针丢弃输出（只测关联加载层耗时），无 golden 语义
        golden = {"golden_ok": None, "rows_read": 0}
    elif skipped is None:
        golden = verify(task["shape"], out_path, full=(task["run"] == 0))
        os.remove(out_path)
    else:
        golden = {"golden_ok": None, "rows_read": 0}
    print(json.dumps({
        "task": kind, "side": task.get("side", "scalim"), "run": task["run"],
        "total_s": body.get("total_s", 0.0), "calls": body.get("calls"),
        "max_inflight": body.get("max_inflight"),
        "rss_hwm_kb": _hwm_kb(), "golden_ok": golden["golden_ok"], "skipped": skipped,
    }))
    return 0


# ---------------------------------------------------------------------------
# py36 容器内 runner（Python 3.6 兼容；引擎路径零三方依赖）
# ---------------------------------------------------------------------------
PY36_INNER = r'''# -*- coding: utf-8 -*-
"""py36 边界探针内嵌 runner（Python 3.6 兼容；scalim 引擎路径零三方依赖）.

宿主机 3.10 与容器 3.6 跑同一份脚本，保证 golden 口径一致。
"""
import json
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.abspath("src"))


def source_row(i):
    return {"id": i, "v0": float(i % 97), "v1": float(i % 13)}


def side_row(sid):
    return {"sid": sid, "s0": (sid % 17) * 1.5, "s1": (sid % 29) * 0.5}


def calc_l0(v0, v1, j):
    return (v0 + v1) if j % 3 == 0 else ((v0 - v1) if j % 3 == 1 else (v0 * v1))


def checksum_targets(n_flat, relation):
    targets = []
    if n_flat:
        targets += ["d0"] + (["d1"] if n_flat > 1 else [])
    if relation:
        targets += ["r0", "r1"]
    return targets


def expected_sums(rows, n_flat, relation, only_first_n=-1):
    sums = dict((t, 0.0) for t in checksum_targets(n_flat, relation))
    limit = rows if only_first_n < 0 else min(rows, only_first_n)
    for i in range(limit):
        v0, v1 = float(i % 97), float(i % 13)
        if "d0" in sums:
            sums["d0"] += calc_l0(v0, v1, 0)
        if "d1" in sums:
            sums["d1"] += calc_l0(v0, v1, 1)
        if relation:
            s = side_row(i % 5000)
            sums["r0"] += v0 + s["s0"]
            sums["r1"] += v1 * s["s1"]
    return sums


def close(a, b):
    return abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))


def hwm_kb():
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith("VmHWM:"):
                return int(line.split()[1])
    return 0


def rss_now_kb():
    with open("/proc/self/statm") as f:
        return int(int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 1024)


def build_and_run(task):
    from scalim.execution.engine import ScalimEngine
    from scalim.execution.runtime_bindings import RuntimeBindings
    from scalim.planning import PlanBuilder
    from scalim.sinks import CSVSink
    from scalim.spec.ir import (BindingIr, CallBySpecIr, CallByValueIr, DemandIr,
                                DerivedFieldIr, FieldIr, KeyIr, LoaderIr, MainSourceIr,
                                RuntimeHandleIdIr, SourceIr)

    shape = task["shape"]
    rows = shape["rows"]
    n_flat = shape["n_flat"]
    relation = bool(shape.get("relation"))
    batch_size = shape.get("batch_size", 500)

    main = MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.loader"))
    ir_fields = [
        FieldIr(field_id="id", name="id", source_id=main.source_id),
        FieldIr(field_id="v0", name="v0", source_id=main.source_id),
        FieldIr(field_id="v1", name="v1", source_id=main.source_id),
    ]
    calculators = {}
    sources = []
    extras = {}
    fields = ["id", "v0", "v1"] + ["d%d" % j for j in range(n_flat)]

    if relation:
        side_loader_ir = LoaderIr(
            callable_ref=RuntimeHandleIdIr(handle_id="side.loader"),
            bindings={"sid": BindingIr(key_field="sid",
                                       params_builder_ref=RuntimeHandleIdIr("side.sid.params_builder"))},
        )
        side = SourceIr(source_id="side", key=KeyIr(key="sid"), loader_spec=side_loader_ir)
        sources = [side]
        rel = main["fk"].join(side["sid"])
        ir_fields.append(FieldIr(field_id="fk", name="fk", source_id=main.source_id))
        ir_fields.append(FieldIr(field_id="s0", name="s0", source_id=side.source_id,
                                 data_key="s0", relation=rel))
        ir_fields.append(FieldIr(field_id="s1", name="s1", source_id=side.source_id,
                                 data_key="s1", relation=rel))

        def side_loader(sids=None):
            keys = sorted(set(sids or ()))
            if not keys:
                return {}
            conn = sqlite3.connect(shape["db"])
            try:
                q = "SELECT sid, s0, s1 FROM side_rows WHERE sid IN (%s)" % ",".join("?" * len(keys))
                return dict((r[0], {"sid": r[0], "s0": r[1], "s1": r[2]}) for r in conn.execute(q, keys))
            finally:
                conn.close()

        def side_params(ctx):
            return (), {"sids": set(ctx.lookup_keys or set())}

        extras["source_loaders"] = {"side": side_loader}
        extras["params_builders"] = {("side", "sid"): side_params}

        def calc_r0(v0, s0):
            return float(v0) + float(s0)

        def calc_r1(v1, s1):
            return float(v1) * float(s1)

        calculators["r0"] = calc_r0
        calculators["r1"] = calc_r1
        for fid, deps, kv in (("r0", ("v0", "s0"), (("v0", "v0"), ("s0", "s0"))),
                              ("r1", ("v1", "s1"), (("v1", "v1"), ("s1", "s1")))):
            ir_fields.append(DerivedFieldIr(
                field_id=fid, name=fid, dependencies=deps,
                call_by=CallBySpecIr(
                    reference=RuntimeHandleIdIr(handle_id=fid + ".calc"),
                    kwargs=tuple((k, CallByValueIr(kind="field", value=v)) for k, v in kv),
                    field_names=deps),
            ))
        fields = fields + ["fk", "s0", "s1", "r0", "r1"]

    for j in range(n_flat):
        fid = "d%d" % j

        def mk(jj):
            def calc(v0, v1):
                return calc_l0(v0, v1, jj)
            return calc

        calculators[fid] = mk(j)
        ir_fields.append(DerivedFieldIr(
            field_id=fid, name=fid, dependencies=("v0", "v1"),
            call_by=CallBySpecIr(
                reference=RuntimeHandleIdIr(handle_id=fid + ".calc"),
                kwargs=(("v0", CallByValueIr(kind="field", value="v0")),
                        ("v1", CallByValueIr(kind="field", value="v1"))),
                field_names=("v0", "v1")),
        ))

    demand = DemandIr.from_irs(sources=sources, fields=tuple(ir_fields),
                               main_source=main, name="py36")
    plan = PlanBuilder(demand).build()
    sink = CSVSink(task["out_path"], field_names=fields, header_names=fields)
    engine = ScalimEngine(
        demand=demand, plan=plan,
        runtime_bindings=RuntimeBindings(main_source_loaders={},
                                         derived_calculators=calculators, **extras),
        batch_size=batch_size, parallel_mode="seq",
    )

    def main_rows():
        if relation:
            conn = sqlite3.connect(shape["db"])
            try:
                for r in conn.execute("SELECT id, fk, v0, v1 FROM main_rows"):
                    yield {"id": r[0], "fk": r[1], "v0": r[2], "v1": r[3]}
            finally:
                conn.close()
        else:
            for i in range(rows):
                yield source_row(i)

    t0 = time.perf_counter()
    engine.run(main_rows=main_rows(), sink=sink)
    return time.perf_counter() - t0


def main():
    task = json.loads(sys.argv[1])
    shape = task["shape"]
    out_path = task["out_path"]
    d = os.path.dirname(out_path)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    before = rss_now_kb()
    elapsed = build_and_run(task)

    rows = shape["rows"]
    n_flat = shape["n_flat"]
    relation = bool(shape.get("relation"))
    with open(out_path) as f:
        lines = f.readlines()
    count = len(lines) - 1
    header = lines[0].strip().split(",")
    targets = checksum_targets(n_flat, relation)
    idx = dict((n, header.index(n)) for n in targets)
    sums = dict((n, 0.0) for n in targets)
    full = task["run"] == 0
    for li, line in enumerate(lines[1:]):
        if not full and li >= 50:
            break
        vals = line.rstrip("\n").split(",")
        for n, ci in idx.items():
            sums[n] += float(vals[ci])
    expected = expected_sums(rows, n_flat, relation) if full else \
        expected_sums(rows, n_flat, relation, only_first_n=50)
    ok = count == rows and all(close(sums[k], expected[k]) for k in targets)
    os.remove(out_path)
    print(json.dumps({"total_s": elapsed, "golden_ok": ok, "rows_read": count,
                      "rss_hwm_kb": hwm_kb(), "rss_begin_kb": before}))


main()
'''


# ---------------------------------------------------------------------------
# 主编排
# ---------------------------------------------------------------------------
def median(xs: List[float]) -> float:
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--probes", type=str, default="sweep-rows,sweep-cols,calc-weight,relation-rtt,py36")
    ap.add_argument("--outdir", type=str, default="")
    args = ap.parse_args()
    smoke = args.scale < 1.0
    assert args.runs >= 3 or smoke, "正式证据要求 --runs >= 3（冒烟除外）"

    probes = [p.strip() for p in args.probes.split(",") if p.strip()]
    ts = time.strftime("%Y%m%d-%H%M%S")
    outdir = args.outdir or os.path.join(REPO_ROOT, ".tmp", "evidence", "external-baseline", "probes", ts)
    os.makedirs(outdir, exist_ok=True)
    py = sys.executable
    this = os.path.abspath(__file__)

    results: List[Dict[str, Any]] = []
    counter = {"n": 0}

    def run_task(task: Dict[str, Any], label: str) -> Optional[Dict[str, Any]]:
        proc = subprocess.run(
            [py, this, "--worker", json.dumps(task)],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        if proc.returncode != 0:
            print(proc.stderr[-3000:], file=sys.stderr)
            print("FAILED: {}".format(label), file=sys.stderr)
            return None
        res = json.loads(proc.stdout.strip().splitlines()[-1])
        counter["n"] += 1
        print("[{:>3}] {}: {:8.3f}s HWM={:8.1f}MiB golden={} {}".format(
            counter["n"], label, res["total_s"], res["rss_hwm_kb"] / 1024.0,
            res.get("golden_ok"), res.get("skipped") or ""), flush=True)
        return res

    out: Dict[str, Any] = {}

    # --- 探针 1/2: 扫参 ---
    sweep_sections: Dict[str, Any] = {}
    for probe, kind in (("sweep-rows", "rows"), ("sweep-cols", "cols")):
        if probe not in probes:
            continue
        points = (SWEEP_ROW_POINTS if kind == "rows" else SWEEP_COL_POINTS)
        entries = []
        for p in points:
            if kind == "rows":
                shape = {"id": "sweep_rows", "rows": scaled(p, args.scale), "n_flat": SWEEP_BASE_FLAT,
                         "sink": "csv", "batch_size": 500}
                x_label, x_val = "rows", p
            else:
                shape = {"id": "sweep_cols", "rows": scaled(SWEEP_BASE_ROWS, args.scale), "n_flat": p,
                         "sink": "csv", "batch_size": 500}
                x_label, x_val = "flat_fields", p
            for side in ("pandas", "polars", "scalim"):
                times: List[float] = []
                hwms: List[float] = []
                ok_all = True
                for run_i in range(args.runs):
                    task = {"kind": "sweep", "side": side, "run": run_i, "shape": dict(shape),
                            "out_path": os.path.join(outdir, "_sweep_{}_{}_{}.csv".format(x_val, side, run_i))}
                    res = run_task(task, "{} x={} {} r{}".format(probe, x_val, side, run_i))
                    if res is None:
                        return 1
                    if not res.get("skipped"):
                        times.append(res["total_s"])
                        hwms.append(res["rss_hwm_kb"] / 1024.0)
                        ok_all = ok_all and bool(res["golden_ok"])
                if times:
                    entries.append({
                        "x": x_val, "side": side,
                        "time_s_median": median(times), "rss_mib_median": median(hwms),
                        "golden_all_ok": ok_all,
                    })
        sweep_sections[kind] = {"x_label": x_label, "points": entries}
    if sweep_sections:
        out["sweeps"] = sweep_sections

    # --- 探针 3: 派生函数复杂度 ---
    if "calc-weight" in probes:
        entries = []
        for level in (0, 1, 2):
            shape = {"id": "calc_L{}".format(level), "rows": scaled(CALC_ROWS, args.scale),
                     "n_flat": CALC_FLAT, "sink": "csv", "batch_size": 500, "calc_level": level}
            for side in ("pandas", "polars", "scalim"):
                times, hwms = [], []
                ok_all = True
                for run_i in range(args.runs):
                    task = {"kind": "calc", "side": side, "run": run_i, "shape": dict(shape),
                            "out_path": os.path.join(outdir, "_calc_L{}_{}_{}.csv".format(level, side, run_i))}
                    res = run_task(task, "calc L{} {} r{}".format(level, side, run_i))
                    if res is None:
                        return 1
                    if not res.get("skipped"):
                        times.append(res["total_s"])
                        hwms.append(res["rss_hwm_kb"] / 1024.0)
                        ok_all = ok_all and bool(res["golden_ok"])
                if times:
                    entries.append({
                        "level": level, "level_label": "L{}({})".format(
                            level, {0: "算术", 1: "十次循环", 2: "百次循环"}[level]),
                        "side": side, "time_s_median": median(times),
                        "rss_mib_median": median(hwms), "golden_all_ok": ok_all,
                    })
        out["calc_weight"] = {"rows": scaled(CALC_ROWS, args.scale), "n_flat": CALC_FLAT, "points": entries}

    # --- 探针 4: 慢源关联分片并行 ---
    if "relation-rtt" in probes:
        entries = []
        for rtt_ms in RTT_POINTS_MS:
            configs = [
                ("full_single", None, "seq", False, 1),
                ("chunk100_serial", 100, "seq", False, 1),
                ("chunk100_parW4", 100, "adaptive", True, 4),
                ("chunk250_parW4", 250, "adaptive", True, 4),
            ]
            for cname, chunk, mode, par, w in configs:
                times, calls, inflights = [], [], []
                for run_i in range(args.runs):
                    rtt_out = os.path.join(outdir, "_rtt_{}_{}_{}.csv".format(rtt_ms, cname, run_i))
                    task = {"kind": "relation", "run": run_i,
                            "config": {"keys": RTT_KEYS, "chunk_size": chunk, "rtt_s": rtt_ms / 1000.0,
                                       "parallel": par, "max_workers": w, "_out_path": rtt_out},
                            "out_path": rtt_out}
                    # relation 探针不走 verify（CSV 只含 fk/s0 丢弃列）；直接调 worker 的 relation 路径
                    proc = subprocess.run(
                        [py, this, "--worker", json.dumps(task)],
                        capture_output=True, text=True, cwd=REPO_ROOT,
                    )
                    if proc.returncode != 0:
                        print(proc.stderr[-3000:], file=sys.stderr)
                        return 1
                    res = json.loads(proc.stdout.strip().splitlines()[-1])
                    counter["n"] += 1
                    times.append(res["total_s"])
                    calls.append(res.get("calls") or 0)
                    inflights.append(res.get("max_inflight") or 0)
                    print("[{:>3}] rtt {}ms {} r{}: {:8.3f}s calls={} infl={}".format(
                        counter["n"], rtt_ms, cname, run_i, res["total_s"], res.get("calls"),
                        res.get("max_inflight")), flush=True)
                entries.append({
                    "rtt_ms": rtt_ms, "config": cname, "chunk_size": chunk,
                    "parallel": par, "max_workers": w,
                    "time_s_median": median(times), "calls_median": median(calls),
                    "max_inflight_median": median(inflights),
                })
        out["relation_rtt"] = {"keys": RTT_KEYS, "points": entries}

    # --- 探针 5: Python 3.6 边界 ---
    if "py36" in probes:
        probes_dir = os.path.join(REPO_ROOT, ".tmp", "evidence", "external-baseline", "probes")
        inner = os.path.join(probes_dir, "py36_inner.py")
        os.makedirs(probes_dir, exist_ok=True)
        with open(inner, "w") as f:
            f.write(PY36_INNER)
        rel_inner = os.path.relpath(inner, REPO_ROOT)
        entries = []
        for shape_t in PY36_SHAPES:
            shape = dict(shape_t)
            shape["rows"] = scaled(shape["rows"], args.scale)
            db = None
            if shape.get("relation"):
                db = os.path.join(outdir, "fixture_py36.sqlite")
                ensure_sqlite_fixture(db, shape["rows"])
            for tag, runner in (("py310", "host"), ("py36", "docker")):
                times, hwms = [], []
                ok_all = True
                for run_i in range(args.runs):
                    rel_out = os.path.join(".tmp", "evidence", "external-baseline", "probes",
                                           "_py36_{}_{}_{}.csv".format(shape["id"], tag, run_i))
                    task = {"shape": {
                        "id": shape["id"], "rows": shape["rows"], "n_flat": shape["n_flat"],
                        "batch_size": shape.get("batch_size", 500), "relation": shape.get("relation", False),
                        "db": os.path.relpath(db, REPO_ROOT) if db else None,
                    }, "run": run_i, "out_path": rel_out}
                    t0 = time.perf_counter()
                    if runner == "host":
                        proc = subprocess.run([py, inner, json.dumps(task)],
                                              capture_output=True, text=True, cwd=REPO_ROOT)
                    else:
                        proc = subprocess.run(
                            ["docker", "run", "--rm", "-v", "{}:/work".format(REPO_ROOT), "-w", "/work",
                             "python:3.6", "python", rel_inner, json.dumps(task)],
                            capture_output=True, text=True, cwd=REPO_ROOT,
                        )
                    wall = time.perf_counter() - t0
                    if proc.returncode != 0:
                        print(proc.stderr[-3000:], file=sys.stderr)
                        print("py36 probe failed: {} {}".format(shape["id"], tag), file=sys.stderr)
                        return 1
                    res = json.loads(proc.stdout.strip().splitlines()[-1])
                    res["parent_wall_s"] = wall
                    counter["n"] += 1
                    times.append(res["total_s"])
                    hwms.append(res["rss_hwm_kb"] / 1024.0)
                    ok_all = ok_all and bool(res["golden_ok"])
                    print("[{:>3}] py36-boundary {} {} r{}: {:8.3f}s HWM={:8.1f}MiB golden={}".format(
                        counter["n"], shape["id"], tag, run_i, res["total_s"],
                        res["rss_hwm_kb"] / 1024.0, res["golden_ok"]), flush=True)
                entries.append({
                    "shape": shape["id"], "python": tag, "runs": len(times),
                    "time_s_median": median(times), "rss_mib_median": median(hwms),
                    "golden_all_ok": ok_all,
                })
        out["py36_boundary"] = {"points": entries}

    versions = {}
    for name in ("python", "scalim", "pandas", "polars", "numpy"):
        try:
            mod = __import__(name)
            versions[name] = str(getattr(mod, "__version__", "unknown"))
        except Exception:
            versions[name] = "not-installed"
    payload = {
        "meta": {
            "timestamp": ts,
            "runs": args.runs,
            "scale": args.scale,
            "versions": versions,
            "host_note": "本机单次调研；跨机器/负载下数字不可直接迁移",
            "method": "子进程隔离墙钟 + VmHWM 真实峰值；golden=run0 全表读回 + 抽样；"
                      "RTT 为 sleep 模拟单次往返；py36 走 docker python:3.6（引擎路径零三方依赖）",
        },
        **out,
    }
    result_path = os.path.join(outdir, "result.json")
    with open(result_path, "w") as f:
        json.dump(payload, f, indent=2)
    print("\nresult.json -> {}".format(result_path))
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--worker":
        sys.exit(worker(json.loads(sys.argv[2])))
    sys.exit(main())
