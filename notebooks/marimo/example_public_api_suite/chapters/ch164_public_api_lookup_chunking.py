"""Cells-native marimo notebook: ch164_public_api_lookup_chunking.

迁移对照:
  Before: 模块级 run_public_api_lookup_chunking() 持全部逻辑(493 行);cells 薄壳
  After:  零件/八种 lookup 形态运行/断言全部在 cells 内
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_public_api_suite / ch164_public_api_lookup_chunking

        本章目标：
        - 黑盒核对 `LookupChunking`：YAML `keys` 关联 + `Observer`/`Hook` `LOADER_CALL`
        - 形态对照：off / default / sized(serial) / sized(N) / batched / parallel /
          seq+parallel / YAML 拒绝 / downstream max_batch

        ## 主线装配过程（每个步骤一个 cell，可就地修改重跑）

        1. 零件：LOADER_CALL 追踪（Observer+Hook 双视角）+ 分块黑盒期望
        2. 内联 demand YAML ×3（含 YAML `lookup_chunk_size` 拒绝样张）
        3. 运行组 1（off/default/serial/oversized）+ 运行组 2（batched/parallel/seq）
        4. YAML reject + limited max_batch 对照
        5. 断言展开：call 序列黑盒核对 + 行一致
        6. 汇总 chapter_result

        Gate: `just examples`
        """
    )
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    import tempfile
    from pathlib import Path
    from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple

    from scalim.dsl import yaml_dsl as api
    from scalim.events import Event, EventType
    from scalim.hooks import BaseHook
    from scalim.ob.observer import Observer
    from scalim_misc.examples.public_api._fixtures import LOOKUP_CHUNK_DEMO_ORDER_COUNT
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    ALLOWED_MODULES: FrozenSet[str] = frozenset(["scalim_misc.examples.public_api._fixtures"])
    N_KEYS = LOOKUP_CHUNK_DEMO_ORDER_COUNT
    CUSTOMER_SOURCE = "customers"
    SERIAL_CHUNK = 3
    DOWNSTREAM_MAX_BATCH = 4

    return (
        ALLOWED_MODULES,
        Any,
        BaseHook,
        CUSTOMER_SOURCE,
        DOWNSTREAM_MAX_BATCH,
        Dict,
        Event,
        EventType,
        FrozenSet,
        List,
        LOOKUP_CHUNK_DEMO_ORDER_COUNT,
        Mapping,
        N_KEYS,
        Observer,
        Optional,
        Path,
        SERIAL_CHUNK,
        Sequence,
        Set,
        Tuple,
        api,
        make_chapter_result,
        render_checks,
        tempfile,
    )


@app.cell
def _(Any, BaseHook, Dict, Event, EventType, List, Mapping, Observer, Optional, Sequence, Set, Tuple):
    # 零件: LOADER_CALL 追踪(Observer+Hook 双视角,加锁并行安全)
    class LoaderCallTrace:
        def __init__(self) -> None:
            import threading

            self._lock = threading.Lock()
            self.calls: List[Dict[str, Any]] = []

        def record(self, event: Event) -> None:
            payload = event.payload
            params = getattr(payload, "params", None)
            ids = None
            if isinstance(params, Mapping):
                ids = params.get("ids")
            ids_len = len(list(ids)) if ids is not None else None
            offset = getattr(payload, "chunk_offset", None)
            count = getattr(payload, "lookup_key_count", None)
            with self._lock:
                self.calls.append(
                    {
                        "loader_name": str(getattr(payload, "loader_name", "") or ""),
                        "lookup_key_count": None if count is None else int(count),
                        "chunk_offset": None if offset is None else int(offset),
                        "ids_len": ids_len,
                        "batch_num": getattr(payload, "batch_num", None),
                        "cache_status": getattr(payload, "cache_status", None),
                    }
                )

        def for_source(self, source_id: str) -> List[Dict[str, Any]]:
            with self._lock:
                return [dict(item) for item in self.calls if item.get("loader_name") == source_id]

    class LoaderCallObserver(Observer):
        def __init__(self, trace: LoaderCallTrace) -> None:
            self.event_types: Optional[Set[EventType]] = {EventType.LOADER_CALL}
            self.trace = trace

        def on_event(self, event: Event) -> None:
            if event.event_type is EventType.LOADER_CALL:
                self.trace.record(event)

    class LoaderCallHook(BaseHook):
        def __init__(self, trace: LoaderCallTrace) -> None:
            self.event_types: Optional[Set[EventType]] = {EventType.LOADER_CALL}
            self.trace = trace

        def on_loader_call(self, event: Event) -> None:
            self.trace.record(event)

    # 零件: 黑盒期望 — size >= unique_keys 时不分片
    def expect_chunked(n_keys: int, size: int) -> Dict[str, Any]:
        if size < 1:
            raise ValueError("chunk size must be >= 1")
        if size >= n_keys:
            return {"chunked": False, "call_count": 1, "offsets": [None], "counts": [n_keys]}
        offsets = list(range(0, n_keys, size))
        counts = [min(size, n_keys - offset) for offset in offsets]
        return {"chunked": True, "call_count": len(offsets), "offsets": offsets, "counts": counts}

    def call_signature(calls: Sequence[Mapping[str, Any]]) -> List[Tuple[Any, Any, Any]]:
        return [(item.get("chunk_offset"), item.get("lookup_key_count"), item.get("ids_len")) for item in calls]

    def rows_from_result(result: Any) -> List[Dict[str, Any]]:
        captured = getattr(result, "captured_rows", None)
        if captured is None:
            return []
        return list(captured.iter_row_data())

    def row_ok(rows: Sequence[Mapping[str, Any]], *, n_keys: int) -> bool:
        if len(rows) != n_keys:
            return False
        for row in rows:
            customer_id = row.get("customer_id")
            expected = "Customer-{}".format(customer_id)
            if row.get("customer_name") != expected:
                return False
        return True

    def caught_message(exc: BaseException) -> str:
        parts = ["{}: {}".format(type(exc).__name__, exc)]
        errors = getattr(exc, "errors", None)
        if errors:
            extra = "\n".join(str(getattr(item, "message", item)) for item in errors)
            if extra:
                parts.append(extra)
        return "\n".join(parts)

    def run_lookup(
        *,
        demand_path: Path,
        lookup_chunking: Mapping[str, api.LookupChunking],
        parallel_mode: str = "seq",
        batch_size: int = 10,
    ) -> Tuple[Any, LoaderCallTrace, LoaderCallTrace, Optional[str]]:
        observer_trace = LoaderCallTrace()
        hook_trace = LoaderCallTrace()
        observer = LoaderCallObserver(observer_trace)
        hook = LoaderCallHook(hook_trace)
        try:
            result = api.run(
                str(demand_path),
                options=api.DemandRunOptions(
                    security=api.DemandRunSecurityOptions(allowed_modules=ALLOWED_MODULES),
                    runtime=api.DemandRunRuntimeOptions(
                        batch_size=batch_size,
                        parallel_mode=parallel_mode,  # type: ignore[arg-type]
                        lookup_chunking=lookup_chunking,
                        components=[observer, hook],
                    ),
                    outputs=api.DemandRunOutputOptions(capture=api.CaptureRows()),
                ),
            )
            return result, observer_trace, hook_trace, None
        except Exception as exc:  # noqa: BLE001
            return None, observer_trace, hook_trace, caught_message(exc)

    def customer_calls_match(observer_trace: LoaderCallTrace, hook_trace: LoaderCallTrace) -> Tuple[List[Dict[str, Any]], bool]:
        observer_calls = observer_trace.for_source(CUSTOMER_SOURCE)
        hook_calls = hook_trace.for_source(CUSTOMER_SOURCE)
        same = call_signature(observer_calls) == call_signature(hook_calls)
        counts_match_ids = all(
            item.get("lookup_key_count") == item.get("ids_len") for item in observer_calls if item.get("ids_len") is not None
        )
        return observer_calls, bool(same and counts_match_ids)

    def check_unchunked(calls: Sequence[Mapping[str, Any]], *, n_keys: int) -> bool:
        return bool(
            len(calls) == 1
            and calls[0].get("chunk_offset") is None
            and calls[0].get("lookup_key_count") == n_keys
            and calls[0].get("ids_len") in (None, n_keys)
        )

    def check_serial_chunked(calls: Sequence[Mapping[str, Any]], *, n_keys: int, size: int) -> bool:
        expected = expect_chunked(n_keys, size)
        if not expected["chunked"]:
            return check_unchunked(calls, n_keys=n_keys)
        offsets = [item.get("chunk_offset") for item in calls]
        counts = [item.get("lookup_key_count") for item in calls]
        return bool(
            len(calls) == expected["call_count"]
            and offsets == expected["offsets"]
            and counts == expected["counts"]
            and all((item.get("ids_len") in (None, item.get("lookup_key_count"))) for item in calls)
            and all(int(item.get("lookup_key_count") or 0) <= size for item in calls)
        )

    def write_text(path: Path, text: str) -> None:
        path.write_text(text, encoding="utf-8")

    def keys_demand_yaml(*, max_batch: Optional[int] = None, lookup_chunk_size: Optional[int] = None) -> str:
        extra_param = ""
        if max_batch is not None:
            extra_param = "      max_batch: {}\n".format(int(max_batch))
        extra_source = ""
        if lookup_chunk_size is not None:
            extra_source = "    lookup_chunk_size: {}\n".format(int(lookup_chunk_size))
        return (
            "name: public_api_lookup_chunking\n"
            "\n"
            "main_source:\n"
            "  source_id: orders\n"
            '  loader: "scalim_misc.examples.public_api._fixtures:load_orders_lookup_chunk_demo"\n'
            "  fields:\n"
            "    order_id: {extract: order_id, name: Order ID}\n"
            "    customer_id: {extract: customer_id, name: Customer ID}\n"
            "    amount: {extract: amount, name: Amount}\n"
            "\n"
            "relations:\n"
            "  orders_to_customers:\n"
            "    steps:\n"
            "      - from: orders.customer_id\n"
            "        to: customers.customer_id\n"
            "\n"
            "sources:\n"
            "  customers:\n"
            '    loader: "scalim_misc.examples.public_api._fixtures:load_customers_by_ids"\n'
            "    key: customer_id\n" + extra_source + "    params:\n"
            "      ids: {$keys: {as: list}}\n" + extra_param + "    fields:\n"
            "      customer_name:\n"
            "        name: Customer Name\n"
            "        relation: orders_to_customers\n"
        )

    return (
        LoaderCallHook,
        LoaderCallObserver,
        LoaderCallTrace,
        call_signature,
        caught_message,
        check_serial_chunked,
        check_unchunked,
        customer_calls_match,
        expect_chunked,
        keys_demand_yaml,
        row_ok,
        rows_from_result,
        run_lookup,
        write_text,
    )


@app.cell
def _(
    ALLOWED_MODULES,
    CUSTOMER_SOURCE,
    DOWNSTREAM_MAX_BATCH,
    N_KEYS,
    Path,
    SERIAL_CHUNK,
    api,
    keys_demand_yaml,
    run_lookup,
    tempfile,
    write_text,
):
    import atexit
    import shutil

    tmp = Path(tempfile.mkdtemp(prefix="scalim-public-api-lookup-chunking-"))
    atexit.register(lambda: shutil.rmtree(tmp, ignore_errors=True))

    demand_path = tmp / "demand.yaml"
    limited_path = tmp / "demand_limited.yaml"
    yaml_reject_path = tmp / "demand_yaml_chunk_size.yaml"
    write_text(demand_path, keys_demand_yaml())
    write_text(limited_path, keys_demand_yaml(max_batch=DOWNSTREAM_MAX_BATCH))
    write_text(yaml_reject_path, keys_demand_yaml(lookup_chunk_size=SERIAL_CHUNK))
    print("tmp dir:", tmp)

    # 运行组 1: off / default / serial / oversized
    off_result, off_obs, off_hook, off_err = run_lookup(
        demand_path=demand_path,
        lookup_chunking={CUSTOMER_SOURCE: api.LookupChunking.off()},
    )
    default_result, default_obs, default_hook, default_err = run_lookup(demand_path=demand_path, lookup_chunking={})
    serial_result, serial_obs, serial_hook, serial_err = run_lookup(
        demand_path=demand_path,
        lookup_chunking={CUSTOMER_SOURCE: api.LookupChunking.sized(SERIAL_CHUNK)},
    )
    oversized_result, oversized_obs, oversized_hook, oversized_err = run_lookup(
        demand_path=demand_path,
        lookup_chunking={CUSTOMER_SOURCE: api.LookupChunking.sized(N_KEYS)},
    )
    return (
        default_err,
        default_hook,
        default_obs,
        default_result,
        demand_path,
        limited_path,
        off_err,
        off_hook,
        off_obs,
        off_result,
        oversized_err,
        oversized_hook,
        oversized_obs,
        oversized_result,
        serial_err,
        serial_hook,
        serial_obs,
        serial_result,
        tmp,
        yaml_reject_path,
    )


@app.cell
def _(ALLOWED_MODULES, CUSTOMER_SOURCE, N_KEYS, SERIAL_CHUNK, api, demand_path, run_lookup):
    # 运行组 2: batched / parallel / seq+parallel
    batched_result, batched_obs, batched_hook, batched_err = run_lookup(
        demand_path=demand_path,
        lookup_chunking={CUSTOMER_SOURCE: api.LookupChunking.sized(SERIAL_CHUNK)},
        batch_size=5,
    )
    parallel_result, parallel_obs, parallel_hook, parallel_err = run_lookup(
        demand_path=demand_path,
        lookup_chunking={CUSTOMER_SOURCE: api.LookupChunking.sized(SERIAL_CHUNK, parallel=True)},
        parallel_mode="adaptive",
    )
    seq_parallel_result, seq_parallel_obs, seq_parallel_hook, seq_parallel_err = run_lookup(
        demand_path=demand_path,
        lookup_chunking={CUSTOMER_SOURCE: api.LookupChunking.sized(SERIAL_CHUNK, parallel=True)},
        parallel_mode="seq",
    )
    return (
        batched_err,
        batched_hook,
        batched_obs,
        batched_result,
        parallel_err,
        parallel_hook,
        parallel_obs,
        parallel_result,
        seq_parallel_err,
        seq_parallel_hook,
        seq_parallel_obs,
        seq_parallel_result,
    )


@app.cell
def _(ALLOWED_MODULES, DOWNSTREAM_MAX_BATCH, CUSTOMER_SOURCE, api, limited_path, run_lookup):
    # limited: max_batch=4 下游 + sized(4)
    limited_off_result, _limited_off_obs, _limited_off_hook, limited_off_err = run_lookup(
        demand_path=limited_path,
        lookup_chunking={CUSTOMER_SOURCE: api.LookupChunking.off()},
    )
    limited_ok_result, limited_ok_obs, limited_ok_hook, limited_ok_err = run_lookup(
        demand_path=limited_path,
        lookup_chunking={CUSTOMER_SOURCE: api.LookupChunking.sized(DOWNSTREAM_MAX_BATCH)},
    )
    return (
        limited_off_err,
        limited_off_result,
        limited_ok_err,
        limited_ok_hook,
        limited_ok_obs,
        limited_ok_result,
    )


@app.cell
def _(ALLOWED_MODULES, api, caught_message, yaml_reject_path):
    # YAML lookup_chunk_size 拒绝
    yaml_err = ""
    try:
        _ = api.run(
            str(yaml_reject_path),
            options=api.DemandRunOptions(
                security=api.DemandRunSecurityOptions(allowed_modules=ALLOWED_MODULES),
                runtime=api.DemandRunRuntimeOptions(batch_size=10),
                outputs=api.DemandRunOutputOptions(capture=api.CaptureRows()),
            ),
        )
    except Exception as exc:  # noqa: BLE001 — 预期异常
        yaml_err = caught_message(exc)
    print("yaml_rejected:", "lookup_chunk_size" in yaml_err and "LookupChunking" in yaml_err)
    return yaml_err


@app.cell
def _(
    DOWNSTREAM_MAX_BATCH,
    N_KEYS,
    SERIAL_CHUNK,
    batched_err,
    batched_hook,
    batched_obs,
    batched_result,
    check_serial_chunked,
    check_unchunked,
    customer_calls_match,
    default_err,
    default_hook,
    default_obs,
    default_result,
    expect_chunked,
    limited_off_err,
    limited_off_result,
    limited_ok_err,
    limited_ok_hook,
    limited_ok_obs,
    limited_ok_result,
    off_err,
    off_hook,
    off_obs,
    off_result,
    oversized_err,
    oversized_hook,
    oversized_obs,
    oversized_result,
    parallel_err,
    parallel_hook,
    parallel_obs,
    parallel_result,
    render_checks,
    row_ok,
    rows_from_result,
    seq_parallel_err,
    seq_parallel_hook,
    seq_parallel_obs,
    seq_parallel_result,
    serial_err,
    serial_hook,
    serial_obs,
    serial_result,
    yaml_err,
):
    # 断言展开: call 序列黑盒核对
    off_calls, off_agree = customer_calls_match(off_obs, off_hook)
    default_calls, default_agree = customer_calls_match(default_obs, default_hook)
    serial_calls, serial_agree = customer_calls_match(serial_obs, serial_hook)
    oversized_calls, oversized_agree = customer_calls_match(oversized_obs, oversized_hook)
    batched_calls, batched_agree = customer_calls_match(batched_obs, batched_hook)
    parallel_calls, parallel_agree = customer_calls_match(parallel_obs, parallel_hook)
    seq_parallel_calls, seq_parallel_agree = customer_calls_match(seq_parallel_obs, seq_parallel_hook)
    limited_ok_calls, limited_ok_agree = customer_calls_match(limited_ok_obs, limited_ok_hook)

    serial_expected = expect_chunked(N_KEYS, SERIAL_CHUNK)
    parallel_offsets = sorted(item.get("chunk_offset") for item in parallel_calls)
    batched_ok = bool(
        len(batched_calls) == 4
        and all(int(item.get("lookup_key_count") or 0) <= SERIAL_CHUNK for item in batched_calls)
        and sorted(item.get("chunk_offset") for item in batched_calls) == [0, 0, 3, 3]
    )

    off_rows = [] if off_result is None else rows_from_result(off_result)
    serial_rows = [] if serial_result is None else rows_from_result(serial_result)
    parallel_rows = [] if parallel_result is None else rows_from_result(parallel_result)
    limited_ok_rows = [] if limited_ok_result is None else rows_from_result(limited_ok_result)

    yaml_rejected = "lookup_chunk_size" in yaml_err and "LookupChunking" in yaml_err
    limited_off_failed = limited_off_result is None and "max_batch" in (limited_off_err or "")
    limited_off_did_not_run = limited_off_result is None

    checks = {
        "全部运行无错误": all(
            err is None
            for err in (off_err, default_err, serial_err, oversized_err, batched_err, parallel_err, seq_parallel_err, limited_ok_err)
        ),
        "Observer/Hook 双视角一致(8 组)": all(
            agree
            for agree in (
                off_agree,
                default_agree,
                serial_agree,
                oversized_agree,
                batched_agree,
                parallel_agree,
                seq_parallel_agree,
                limited_ok_agree,
            )
        ),
        "off/default/oversized 不分片": check_unchunked(off_calls, n_keys=N_KEYS)
        and check_unchunked(default_calls, n_keys=N_KEYS)
        and check_unchunked(oversized_calls, n_keys=N_KEYS),
        "serial 分片黑盒一致": check_serial_chunked(serial_calls, n_keys=N_KEYS, size=SERIAL_CHUNK),
        "seq+parallel 分片一致": check_serial_chunked(seq_parallel_calls, n_keys=N_KEYS, size=SERIAL_CHUNK),
        "parallel 分片=串行期望": len(parallel_calls) == serial_expected["call_count"] and parallel_offsets == serial_expected["offsets"],
        "batched 两轮四调用": batched_ok,
        "YAML lookup_chunk_size 拒绝": yaml_rejected,
        "limited max_batch 冲突失败": limited_off_failed and limited_off_did_not_run,
        "limited sized(4) 分片一致": check_serial_chunked(limited_ok_calls, n_keys=N_KEYS, size=DOWNSTREAM_MAX_BATCH),
        "行对拍(off/serial/parallel/limited)": row_ok(off_rows, n_keys=N_KEYS)
        and row_ok(serial_rows, n_keys=N_KEYS)
        and row_ok(parallel_rows, n_keys=N_KEYS)
        and row_ok(limited_ok_rows, n_keys=N_KEYS)
        and serial_rows == off_rows
        and parallel_rows == off_rows,
    }
    render_checks(checks)
    return (
        batched_calls,
        checks,
        default_calls,
        limited_ok_calls,
        off_calls,
        oversized_calls,
        parallel_calls,
        seq_parallel_calls,
        serial_calls,
    )


@app.cell
def _(
    N_KEYS,
    SERIAL_CHUNK,
    batched_calls,
    batched_err,
    checks,
    default_calls,
    default_err,
    limited_off_err,
    limited_off_result,
    limited_ok_calls,
    limited_ok_err,
    make_chapter_result,
    off_calls,
    off_err,
    oversized_calls,
    oversized_err,
    parallel_calls,
    parallel_err,
    seq_parallel_calls,
    seq_parallel_err,
    serial_calls,
    serial_err,
    yaml_err,
):
    passed = bool(all(checks.values()))
    summary = "off={} serial={} parallel={} oversized={} batched={} yaml_reject={} limited_off_fail={} limited_ok={}".format(
        len(off_calls),
        len(serial_calls),
        len(parallel_calls),
        len(oversized_calls),
        len(batched_calls),
        "lookup_chunk_size" in yaml_err,
        limited_off_result is None,
        len(limited_ok_calls),
    )
    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "off": off_calls,
            "default": default_calls,
            "serial": serial_calls,
            "oversized": oversized_calls,
            "batched": batched_calls,
            "parallel": parallel_calls,
            "seq_parallel": seq_parallel_calls,
            "limited_ok": limited_ok_calls,
            "yaml_err": yaml_err,
            "limited_off_err": limited_off_err,
            "errors": {
                "off": off_err,
                "default": default_err,
                "serial": serial_err,
                "oversized": oversized_err,
                "batched": batched_err,
                "parallel": parallel_err,
                "seq_parallel": seq_parallel_err,
                "limited_ok": limited_ok_err,
            },
            "n_keys": N_KEYS,
            "serial_chunk": SERIAL_CHUNK,
            "checks": {k: bool(v) for k, v in checks.items()},
        },
    )
    return chapter_result, passed, summary


@app.cell(hide_code=True)
def _(chapter_result, mo):
    mo.callout(
        mo.md("## {}: {}".format("✅ PASS" if chapter_result["passed"] else "❌ FAIL", chapter_result["summary"])),
        kind="success" if chapter_result["passed"] else "danger",
    )
    return


@app.cell(hide_code=True)
def _(chapter_result, mo):
    from scalim_misc.notebook_support.results_view import details_to_rows

    table_rows = details_to_rows(chapter_result["details"])
    mo.ui.table(table_rows, selection=None) if table_rows else mo.md("(无详情)")
    return


def run_chapter():
    """SSOT 入口：headless runner 与 pytest 通过此函数执行对拍。"""
    outputs, defs = app.run()
    return defs["chapter_result"]


if __name__ == "__main__":
    app.run()
