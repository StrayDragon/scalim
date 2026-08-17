import marimo

import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple

from scalim.dsl import yaml_dsl as api
from scalim.events import Event, EventType
from scalim.hooks import BaseHook
from scalim.ob.observer import Observer
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult
from scalim_misc.examples.public_api._fixtures import LOOKUP_CHUNK_DEMO_ORDER_COUNT

__generated_with = "0.22.0"
app = marimo.App(width="full")

_ALLOWED_MODULES: FrozenSet[str] = frozenset(["scalim_misc.examples.public_api._fixtures"])
_EXAMPLE_ID = "example_public_api_suite/ch164_public_api_lookup_chunking"
_CUSTOMER_SOURCE = "customers"
_N_KEYS = LOOKUP_CHUNK_DEMO_ORDER_COUNT
_SERIAL_CHUNK = 3
_DOWNSTREAM_MAX_BATCH = 4


class _LoaderCallTrace:
    """Observer / Hook 共用的 `LOADER_CALL` 记录(并行路径须加锁)."""

    def __init__(self) -> None:
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


class _LoaderCallObserver(Observer):
    def __init__(self, trace: _LoaderCallTrace) -> None:
        self.event_types: Optional[Set[EventType]] = {EventType.LOADER_CALL}
        self.trace = trace

    def on_event(self, event: Event) -> None:
        if event.event_type is EventType.LOADER_CALL:
            self.trace.record(event)


class _LoaderCallHook(BaseHook):
    def __init__(self, trace: _LoaderCallTrace) -> None:
        self.event_types: Optional[Set[EventType]] = {EventType.LOADER_CALL}
        self.trace = trace

    def on_loader_call(self, event: Event) -> None:
        self.trace.record(event)


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _keys_demand_yaml(*, max_batch: Optional[int] = None, lookup_chunk_size: Optional[int] = None) -> str:
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
        "    key: customer_id\n"
        + extra_source
        + "    params:\n"
        "      ids: {$keys: {as: list}}\n"
        + extra_param
        + "    fields:\n"
        "      customer_name:\n"
        "        name: Customer Name\n"
        "        relation: orders_to_customers\n"
    )


def _caught_message(exc: BaseException) -> str:
    parts = ["{}: {}".format(type(exc).__name__, exc)]
    errors = getattr(exc, "errors", None)
    if errors:
        extra = "\n".join(str(getattr(item, "message", item)) for item in errors)
        if extra:
            parts.append(extra)
    return "\n".join(parts)


def _expect_chunked(n_keys: int, size: int) -> Dict[str, Any]:
    """与运行时相同的黑盒规则: `size >= unique_keys` 时不分片(无 `chunk_offset`)."""

    if size < 1:
        raise ValueError("chunk size must be >= 1")
    if size >= n_keys:
        return {"chunked": False, "call_count": 1, "offsets": [None], "counts": [n_keys]}
    offsets = list(range(0, n_keys, size))
    counts = [min(size, n_keys - offset) for offset in offsets]
    return {"chunked": True, "call_count": len(offsets), "offsets": offsets, "counts": counts}


def _call_signature(calls: Sequence[Mapping[str, Any]]) -> List[Tuple[Any, Any, Any]]:
    return [(item.get("chunk_offset"), item.get("lookup_key_count"), item.get("ids_len")) for item in calls]


def _rows_from_result(result: Any) -> List[Dict[str, Any]]:
    captured = getattr(result, "captured_rows", None)
    if captured is None:
        return []
    return list(captured.iter_row_data())


def _row_ok(rows: Sequence[Mapping[str, Any]]) -> bool:
    if len(rows) != _N_KEYS:
        return False
    for row in rows:
        customer_id = row.get("customer_id")
        expected = "Customer-{}".format(customer_id)
        if row.get("customer_name") != expected:
            return False
    return True


def _run_lookup(
    *,
    demand_path: Path,
    lookup_chunking: Mapping[str, api.LookupChunking],
    parallel_mode: str = "seq",
    batch_size: int = 10,
) -> Tuple[Any, _LoaderCallTrace, _LoaderCallTrace, Optional[str]]:
    observer_trace = _LoaderCallTrace()
    hook_trace = _LoaderCallTrace()
    observer = _LoaderCallObserver(observer_trace)
    hook = _LoaderCallHook(hook_trace)
    try:
        result = api.run(
            str(demand_path),
            options=api.DemandRunOptions(
                security=api.DemandRunSecurityOptions(allowed_modules=_ALLOWED_MODULES),
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
        return None, observer_trace, hook_trace, _caught_message(exc)


def _customer_calls_match(observer_trace: _LoaderCallTrace, hook_trace: _LoaderCallTrace) -> Tuple[List[Dict[str, Any]], bool]:
    observer_calls = observer_trace.for_source(_CUSTOMER_SOURCE)
    hook_calls = hook_trace.for_source(_CUSTOMER_SOURCE)
    same = _call_signature(observer_calls) == _call_signature(hook_calls)
    counts_match_ids = all(
        item.get("lookup_key_count") == item.get("ids_len") for item in observer_calls if item.get("ids_len") is not None
    )
    return observer_calls, bool(same and counts_match_ids)


def _check_unchunked(calls: Sequence[Mapping[str, Any]], *, n_keys: int) -> bool:
    return bool(
        len(calls) == 1
        and calls[0].get("chunk_offset") is None
        and calls[0].get("lookup_key_count") == n_keys
        and calls[0].get("ids_len") in (None, n_keys)
    )


def _check_serial_chunked(calls: Sequence[Mapping[str, Any]], *, n_keys: int, size: int) -> bool:
    expected = _expect_chunked(n_keys, size)
    if not expected["chunked"]:
        return _check_unchunked(calls, n_keys=n_keys)
    offsets = [item.get("chunk_offset") for item in calls]
    counts = [item.get("lookup_key_count") for item in calls]
    return bool(
        len(calls) == expected["call_count"]
        and offsets == expected["offsets"]
        and counts == expected["counts"]
        and all((item.get("ids_len") in (None, item.get("lookup_key_count"))) for item in calls)
        and all(int(item.get("lookup_key_count") or 0) <= size for item in calls)
    )


def run_public_api_lookup_chunking() -> ExampleResult:
    """黑盒核对 `LookupChunking`: YAML keys lookup + Observer/Hook `LOADER_CALL`."""

    with tempfile.TemporaryDirectory(prefix="scalim-public-api-lookup-chunking-") as tmpdir:
        tmp = Path(tmpdir)
        demand_path = tmp / "demand.yaml"
        limited_path = tmp / "demand_limited.yaml"
        yaml_reject_path = tmp / "demand_yaml_chunk_size.yaml"
        _write_text(demand_path, _keys_demand_yaml())
        _write_text(limited_path, _keys_demand_yaml(max_batch=_DOWNSTREAM_MAX_BATCH))
        _write_text(yaml_reject_path, _keys_demand_yaml(lookup_chunk_size=_SERIAL_CHUNK))

        off_result, off_obs, off_hook, off_err = _run_lookup(
            demand_path=demand_path,
            lookup_chunking={_CUSTOMER_SOURCE: api.LookupChunking.off()},
        )
        default_result, default_obs, default_hook, default_err = _run_lookup(
            demand_path=demand_path,
            lookup_chunking={},
        )
        serial_result, serial_obs, serial_hook, serial_err = _run_lookup(
            demand_path=demand_path,
            lookup_chunking={_CUSTOMER_SOURCE: api.LookupChunking.sized(_SERIAL_CHUNK)},
        )
        oversized_result, oversized_obs, oversized_hook, oversized_err = _run_lookup(
            demand_path=demand_path,
            lookup_chunking={_CUSTOMER_SOURCE: api.LookupChunking.sized(_N_KEYS)},
        )
        batched_result, batched_obs, batched_hook, batched_err = _run_lookup(
            demand_path=demand_path,
            lookup_chunking={_CUSTOMER_SOURCE: api.LookupChunking.sized(_SERIAL_CHUNK)},
            batch_size=5,
        )
        parallel_result, parallel_obs, parallel_hook, parallel_err = _run_lookup(
            demand_path=demand_path,
            lookup_chunking={_CUSTOMER_SOURCE: api.LookupChunking.sized(_SERIAL_CHUNK, parallel=True)},
            parallel_mode="adaptive",
        )
        seq_parallel_result, seq_parallel_obs, seq_parallel_hook, seq_parallel_err = _run_lookup(
            demand_path=demand_path,
            lookup_chunking={_CUSTOMER_SOURCE: api.LookupChunking.sized(_SERIAL_CHUNK, parallel=True)},
            parallel_mode="seq",
        )

        limited_off_result, _limited_off_obs, _limited_off_hook, limited_off_err = _run_lookup(
            demand_path=limited_path,
            lookup_chunking={_CUSTOMER_SOURCE: api.LookupChunking.off()},
        )
        limited_ok_result, limited_ok_obs, limited_ok_hook, limited_ok_err = _run_lookup(
            demand_path=limited_path,
            lookup_chunking={_CUSTOMER_SOURCE: api.LookupChunking.sized(_DOWNSTREAM_MAX_BATCH)},
        )

        yaml_err = ""
        try:
            _ = api.run(
                str(yaml_reject_path),
                options=api.DemandRunOptions(
                    security=api.DemandRunSecurityOptions(allowed_modules=_ALLOWED_MODULES),
                    runtime=api.DemandRunRuntimeOptions(batch_size=10),
                    outputs=api.DemandRunOutputOptions(capture=api.CaptureRows()),
                ),
            )
        except Exception as exc:  # noqa: BLE001
            yaml_err = _caught_message(exc)

        off_calls, off_agree = _customer_calls_match(off_obs, off_hook)
        default_calls, default_agree = _customer_calls_match(default_obs, default_hook)
        serial_calls, serial_agree = _customer_calls_match(serial_obs, serial_hook)
        oversized_calls, oversized_agree = _customer_calls_match(oversized_obs, oversized_hook)
        batched_calls, batched_agree = _customer_calls_match(batched_obs, batched_hook)
        parallel_calls, parallel_agree = _customer_calls_match(parallel_obs, parallel_hook)
        seq_parallel_calls, seq_parallel_agree = _customer_calls_match(seq_parallel_obs, seq_parallel_hook)
        limited_ok_calls, limited_ok_agree = _customer_calls_match(limited_ok_obs, limited_ok_hook)

        serial_expected = _expect_chunked(_N_KEYS, _SERIAL_CHUNK)
        parallel_offsets = sorted(item.get("chunk_offset") for item in parallel_calls)
        batched_expected_calls = 4
        batched_ok = bool(
            len(batched_calls) == batched_expected_calls
            and all(int(item.get("lookup_key_count") or 0) <= _SERIAL_CHUNK for item in batched_calls)
            and sorted(item.get("chunk_offset") for item in batched_calls) == [0, 0, 3, 3]
        )

        off_rows = [] if off_result is None else _rows_from_result(off_result)
        serial_rows = [] if serial_result is None else _rows_from_result(serial_result)
        parallel_rows = [] if parallel_result is None else _rows_from_result(parallel_result)
        limited_ok_rows = [] if limited_ok_result is None else _rows_from_result(limited_ok_result)

        yaml_rejected = "lookup_chunk_size" in yaml_err and "LookupChunking" in yaml_err
        limited_off_failed = limited_off_result is None and "max_batch" in (limited_off_err or "")
        limited_off_did_not_run = limited_off_result is None

        passed = bool(
            off_err is None
            and default_err is None
            and serial_err is None
            and oversized_err is None
            and batched_err is None
            and parallel_err is None
            and seq_parallel_err is None
            and limited_ok_err is None
            and off_agree
            and default_agree
            and serial_agree
            and oversized_agree
            and batched_agree
            and parallel_agree
            and seq_parallel_agree
            and limited_ok_agree
            and _check_unchunked(off_calls, n_keys=_N_KEYS)
            and _check_unchunked(default_calls, n_keys=_N_KEYS)
            and _check_unchunked(oversized_calls, n_keys=_N_KEYS)
            and _check_serial_chunked(serial_calls, n_keys=_N_KEYS, size=_SERIAL_CHUNK)
            and _check_serial_chunked(seq_parallel_calls, n_keys=_N_KEYS, size=_SERIAL_CHUNK)
            and len(parallel_calls) == serial_expected["call_count"]
            and parallel_offsets == serial_expected["offsets"]
            and batched_ok
            and yaml_rejected
            and limited_off_failed
            and limited_off_did_not_run
            and _check_serial_chunked(limited_ok_calls, n_keys=_N_KEYS, size=_DOWNSTREAM_MAX_BATCH)
            and _row_ok(off_rows)
            and _row_ok(serial_rows)
            and _row_ok(parallel_rows)
            and _row_ok(limited_ok_rows)
            and serial_rows == off_rows
            and parallel_rows == off_rows
            and default_result is not None
            and oversized_result is not None
            and batched_result is not None
            and seq_parallel_result is not None
        )
        summary = (
            "off={} serial={} parallel={} oversized={} batched={} "
            "yaml_reject={} limited_off_fail={} limited_ok={} rows_eq={}"
        ).format(
            len(off_calls),
            len(serial_calls),
            len(parallel_calls),
            len(oversized_calls),
            len(batched_calls),
            yaml_rejected,
            limited_off_failed,
            len(limited_ok_calls),
            serial_rows == off_rows == parallel_rows,
        )
        details: Dict[str, Any] = {
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
            "n_keys": _N_KEYS,
            "serial_chunk": _SERIAL_CHUNK,
        }
        return ExampleResult(
            example_id=_EXAMPLE_ID,
            passed=passed,
            kind=EXAMPLE_KIND_ORACLE,
            summary=summary,
            details=details,
        )


def run_chapter() -> ExampleResult:
    return run_public_api_lookup_chunking()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_public_api_suite / ch164_public_api_lookup_chunking

        本章目标(黑盒,按使用方路径):
        - YAML 只声明 keys lookup(`params.ids: {$keys: {as: list}}`);分片旋钮在 Python `LookupChunking`
        - 用 Observer + Hook 订阅 `LOADER_CALL`,核对 `lookup_key_count` / `chunk_offset` / 实际 `ids` 长度
        - 默认 / `off()` / `sized(N>=unique_keys)` 都不分片(`chunk_offset is None`,一次 loader 调用)
        - `sized(3)` 串行: 10 keys → 4 次调用, offset `0,3,6,9`
        - `sized(..., parallel=True)` 仍须 `parallel_mode=adaptive`;`seq` 下即使 parallel=True 也保持串行序
        - `batch_size` 切主行,`LookupChunking` 切单次 LoadRef 的 keys,两者正交
        - **何时用**: 下游有硬批次上限时(`max_batch=4`);不分片会失败,`sized(4)` 才跑通
        - YAML 再写 `lookup_chunk_size` fail-fast
        - 行结果在 off / serial / parallel 下一致

        推荐写法:
        ```python
        from scalim.dsl.yaml_dsl import DemandRunRuntimeOptions, LookupChunking
        DemandRunRuntimeOptions(
            lookup_chunking={"customers": LookupChunking.sized(800)},
            # LookupChunking.sized(800, parallel=True), parallel_mode="adaptive"
        )
        ```

        SSOT:
        - `notebooks/marimo/example_public_api_suite/chapters/ch164_public_api_lookup_chunking.py::run_public_api_lookup_chunking`
        - 人类文档: `docs/doc/yaml-dsl/user-guide.md` §4.4.3
        - agent: `agentdev/skills/scalim-yaml-dsl/references/lookup-chunking-guidance.md`

        Gate:
        - `just examples`
        - `pytest -q tests/public_api/test_example_public_api_suite.py --no-cov`
        """
    )
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path

    _ = ensure_repo_root_on_sys_path(__file__)
    return


@app.cell
def _():
    result = run_public_api_lookup_chunking()
    chapter_result = {
        "passed": result.passed,
        "summary": result.summary,
        "details": result.details if result.details is not None else {},
    }
    return (chapter_result,)


@app.cell(hide_code=True)
def _(mo, chapter_result):
    mo.callout(
        mo.md("## {}".format("PASS" if chapter_result["passed"] else "FAIL")),
        kind="success" if chapter_result["passed"] else "danger",
    )
    mo.md("```\n{}\n```".format(chapter_result["summary"]))
    return


@app.cell(hide_code=True)
def _(mo, chapter_result):
    from scalim_misc.notebook_support.results_view import details_to_rows

    rows = details_to_rows(chapter_result["details"])
    mo.ui.table(rows, selection=None)
    return (rows,)


if __name__ == "__main__":
    app.run()
