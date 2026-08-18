import marimo

import csv
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple

from scalim.dsl import yaml_dsl as api
from scalim.events import WORKFLOW_NODE_ID_META_KEY, Event, EventType
from scalim.hooks import BaseHook
from scalim.ob.observer import Observer
from scalim.spec.ir import FieldIr, LookupStepIr, SourceIr
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult
from scalim_misc.examples.public_api._fixtures import (
    WORKFLOW_CATALOG_ALPHA_ORDER_COUNT,
    WORKFLOW_CATALOG_BETA_ORDER_COUNT,
)

__generated_with = "0.22.0"
app = marimo.App(width="full")

_ALLOWED_MODULES: FrozenSet[str] = frozenset(["scalim_misc.examples.public_api._fixtures"])
_EXAMPLE_ID = "example_public_api_suite/ch166_public_api_source_catalog_workflow"
_CUSTOMER_SOURCE = "customers"
_CHUNK_SIZE = 2
_ALPHA_RUN = "alpha"
_BETA_RUN = "beta"


class _LoaderCallTrace:
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
        meta = event.meta or {}
        with self._lock:
            self.calls.append(
                {
                    "loader_name": str(getattr(payload, "loader_name", "") or ""),
                    "lookup_key_count": None if count is None else int(count),
                    "chunk_offset": None if offset is None else int(offset),
                    "ids_len": ids_len,
                    "cache_status": getattr(payload, "cache_status", None),
                    "workflow_node_id": str(meta.get(WORKFLOW_NODE_ID_META_KEY) or ""),
                }
            )

    def for_source(self, source_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(item) for item in self.calls if item.get("loader_name") == source_id]

    def for_node_source(self, workflow_node_id: str, source_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                dict(item)
                for item in self.calls
                if item.get("loader_name") == source_id and item.get("workflow_node_id") == workflow_node_id
            ]


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


def _demand_yaml(*, name: str, orders_loader: str, customers_loader: str, output_dir: Path, file_id: str) -> str:
    csv_dir = str(output_dir).replace("\\", "/")
    return (
        "name: {name}\n"
        "\n"
        "main_source:\n"
        "  source_id: orders\n"
        '  loader: "scalim_misc.examples.public_api._fixtures:{orders_loader}"\n'
        "  fields:\n"
        "    order_id: {{extract: order_id, name: Order ID}}\n"
        "    customer_id: {{extract: customer_id, name: Customer ID}}\n"
        "\n"
        "relations:\n"
        "  orders_to_customers:\n"
        "    steps:\n"
        "      - from: orders.customer_id\n"
        "        to: customers.customer_id\n"
        "\n"
        "sources:\n"
        "  customers:\n"
        '    loader: "scalim_misc.examples.public_api._fixtures:{customers_loader}"\n'
        "    key: customer_id\n"
        "    params:\n"
        "      ids: {{$keys: {{as: list}}}}\n"
        "    fields:\n"
        "      customer_name:\n"
        "        name: Customer Name\n"
        "        relation: orders_to_customers\n"
        "\n"
        "resources:\n"
        "  files:\n"
        "    {file_id}:\n"
        "      csv_file:\n"
        "        path: {csv_dir}\n"
        "\n"
        "outputs:\n"
        "  - name: detail\n"
        "    to: {{file: {file_id}}}\n"
        "    fields: [order_id, customer_id, customer_name]\n"
        "    write:\n"
        "      include_header: true\n"
        "      header_fields_output_by: field_id\n"
    ).format(
        name=name,
        orders_loader=orders_loader,
        customers_loader=customers_loader,
        csv_dir=csv_dir,
        file_id=file_id,
    )


def _expect_chunked(n_keys: int, size: int) -> Dict[str, Any]:
    if size >= n_keys:
        return {"call_count": 1, "offsets": [None], "counts": [n_keys]}
    offsets = list(range(0, n_keys, size))
    counts = [min(size, n_keys - offset) for offset in offsets]
    return {"call_count": len(offsets), "offsets": offsets, "counts": counts}


def _call_signature(calls: Sequence[Mapping[str, Any]]) -> List[Tuple[Any, Any, Any]]:
    return [(item.get("chunk_offset"), item.get("lookup_key_count"), item.get("ids_len")) for item in calls]


def _rows_from_result(result: Any) -> List[Dict[str, Any]]:
    captured = getattr(result, "captured_rows", None)
    if captured is None:
        return []
    return list(captured.iter_row_data())


def _names_ok(rows: Sequence[Mapping[str, Any]], *, prefix: str, n_keys: int) -> bool:
    if len(rows) != n_keys:
        return False
    for row in rows:
        customer_id = row.get("customer_id")
        if row.get("customer_name") != "{}-{}".format(prefix, customer_id):
            return False
    return True


def _chunk_ok(calls: Sequence[Mapping[str, Any]], *, n_keys: int, size: int) -> bool:
    expected = _expect_chunked(n_keys, size)
    offsets = [item.get("chunk_offset") for item in calls]
    counts = [item.get("lookup_key_count") for item in calls]
    return bool(len(calls) == expected["call_count"] and offsets == expected["offsets"] and counts == expected["counts"])


def _demand_options(
    *,
    components: Optional[List[Any]] = None,
) -> api.DemandRunOptions:
    return api.DemandRunOptions(
        security=api.DemandRunSecurityOptions(allowed_modules=_ALLOWED_MODULES),
        runtime=api.DemandRunRuntimeOptions(
            batch_size=10,
            lookup_chunking={_CUSTOMER_SOURCE: api.LookupChunking.sized(_CHUNK_SIZE)},
            components=components,
        ),
        outputs=api.DemandRunOutputOptions(capture=api.CaptureRows()),
    )


def _csv_names(path: Path) -> List[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return [str(row.get("customer_name") or "") for row in rows]


def _catalog_live(compilation: api.Compilation) -> Tuple[SourceIr, FieldIr, LookupStepIr]:
    demand_ir = compilation.demand_ir
    live = SourceIr.from_catalog(demand_ir.sources, _CUSTOMER_SOURCE)
    field = demand_ir.fields["customer_name"]
    if not isinstance(field, FieldIr):
        raise TypeError("customer_name must be FieldIr")
    steps = field.lookup_steps or ()
    if not steps:
        raise ValueError("customer_name lookup_steps missing after compile intern")
    return live, field, steps[0]


def run_public_api_source_catalog_workflow() -> ExampleResult:
    from scalim.dsl.yaml_dsl import workflow_types as workflow_types_api

    observer_trace = _LoaderCallTrace()
    hook_trace = _LoaderCallTrace()
    shared_observer = _LoaderCallObserver(observer_trace)
    shared_hook = _LoaderCallHook(hook_trace)
    runtime_options = _demand_options(components=[shared_observer, shared_hook])

    with tempfile.TemporaryDirectory(prefix="scalim-source-catalog-wf-") as tmpdir:
        tmp = Path(tmpdir)
        alpha_dir = tmp / "alpha_out"
        beta_dir = tmp / "beta_out"
        alpha_dir.mkdir()
        beta_dir.mkdir()
        alpha_path = tmp / "alpha.yaml"
        beta_path = tmp / "beta.yaml"
        workflow_path = tmp / "workflow.yaml"
        _write_text(
            alpha_path,
            _demand_yaml(
                name="catalog_alpha",
                orders_loader="load_orders_catalog_alpha",
                customers_loader="load_customers_catalog_alpha_by_ids",
                output_dir=alpha_dir,
                file_id="alpha_csv",
            ),
        )
        _write_text(
            beta_path,
            _demand_yaml(
                name="catalog_beta",
                orders_loader="load_orders_catalog_beta",
                customers_loader="load_customers_catalog_beta_by_ids",
                output_dir=beta_dir,
                file_id="beta_csv",
            ),
        )
        _write_text(
            workflow_path,
            "workflow:\n  runs:\n    - id: {}\n      demand: alpha.yaml\n    - id: {}\n      demand: beta.yaml\n".format(
                _ALPHA_RUN, _BETA_RUN
            ),
        )

        alpha_compile = api.compile(str(alpha_path), options=runtime_options)
        beta_compile = api.compile(str(beta_path), options=runtime_options)
        alpha_live, alpha_field, alpha_step = _catalog_live(alpha_compile)
        beta_live, beta_field, beta_step = _catalog_live(beta_compile)
        catalogs_isolated = alpha_live is not beta_live
        graph_is_id = (
            alpha_field.source_id == _CUSTOMER_SOURCE
            and beta_field.source_id == _CUSTOMER_SOURCE
            and alpha_step.to_source_id == _CUSTOMER_SOURCE
            and beta_step.to_source_id == _CUSTOMER_SOURCE
            and not hasattr(alpha_step, "to_source")
            and not hasattr(beta_step, "to_source")
        )
        overlay_sized = alpha_live.lookup_chunk_size == _CHUNK_SIZE and beta_live.lookup_chunk_size == _CHUNK_SIZE

        alpha_solo = api.run(str(alpha_path), options=runtime_options)
        beta_solo = api.run(str(beta_path), options=runtime_options)
        alpha_solo_rows = _rows_from_result(alpha_solo)
        beta_solo_rows = _rows_from_result(beta_solo)

        from scalim.shortcuts.resources import outputs as resource_outputs

        api.run_workflow(
            str(workflow_path),
            options=api.WorkflowRunOptions(
                demand=runtime_options,
                patches_by_run_id={
                    _ALPHA_RUN: workflow_types_api.WorkflowNodePatch(),
                    _BETA_RUN: workflow_types_api.WorkflowNodePatch(),
                },
            ),
        )
        alpha_csv = resource_outputs.latest_file_path(alpha_dir, file_id="alpha_csv")
        beta_csv = resource_outputs.latest_file_path(beta_dir, file_id="beta_csv")
        alpha_csv_names = _csv_names(alpha_csv)
        beta_csv_names = _csv_names(beta_csv)
        alpha_solo_names = [row.get("customer_name") for row in alpha_solo_rows]
        beta_solo_names = [row.get("customer_name") for row in beta_solo_rows]
        pair_ok = alpha_csv_names == alpha_solo_names and beta_csv_names == beta_solo_names

        alpha_obs = observer_trace.for_node_source(_ALPHA_RUN, _CUSTOMER_SOURCE)
        beta_obs = observer_trace.for_node_source(_BETA_RUN, _CUSTOMER_SOURCE)
        observer_hook_match = _call_signature(observer_trace.for_source(_CUSTOMER_SOURCE)) == _call_signature(
            hook_trace.for_source(_CUSTOMER_SOURCE)
        )
        alpha_chunked = _chunk_ok(alpha_obs, n_keys=WORKFLOW_CATALOG_ALPHA_ORDER_COUNT, size=_CHUNK_SIZE)
        beta_chunked = _chunk_ok(beta_obs, n_keys=WORKFLOW_CATALOG_BETA_ORDER_COUNT, size=_CHUNK_SIZE)
        alpha_names = _names_ok(alpha_solo_rows, prefix="Alpha", n_keys=WORKFLOW_CATALOG_ALPHA_ORDER_COUNT)
        beta_names = _names_ok(beta_solo_rows, prefix="Beta", n_keys=WORKFLOW_CATALOG_BETA_ORDER_COUNT)
        overlap_not_leaked = all(row.get("customer_name") == "Beta-{}".format(row.get("customer_id")) for row in beta_solo_rows) and all(
            row.get("customer_name") == "Alpha-{}".format(row.get("customer_id")) for row in alpha_solo_rows
        )

        passed = bool(
            catalogs_isolated
            and graph_is_id
            and overlay_sized
            and observer_hook_match
            and alpha_chunked
            and beta_chunked
            and alpha_names
            and beta_names
            and overlap_not_leaked
            and pair_ok
        )
        summary = (
            "isolated={} graph_id={} overlay={} hook_ob={} alpha_chunk={} beta_chunk={} names_ok={}/{} overlap_ok={} pair={}"
        ).format(
            catalogs_isolated,
            graph_is_id,
            overlay_sized,
            observer_hook_match,
            alpha_chunked,
            beta_chunked,
            alpha_names,
            beta_names,
            overlap_not_leaked,
            pair_ok,
        )
        details: Dict[str, Any] = {
            "alpha_lookup_chunk_size": alpha_live.lookup_chunk_size,
            "beta_lookup_chunk_size": beta_live.lookup_chunk_size,
            "alpha_source_id": alpha_field.source_id,
            "beta_to_source_id": beta_step.to_source_id,
            "alpha_loader_calls": _call_signature(alpha_obs),
            "beta_loader_calls": _call_signature(beta_obs),
            "alpha_names": alpha_solo_names,
            "beta_names": beta_solo_names,
            "alpha_csv_names": alpha_csv_names,
            "beta_csv_names": beta_csv_names,
        }
        return ExampleResult(
            example_id=_EXAMPLE_ID,
            passed=passed,
            kind=EXAMPLE_KIND_ORACLE,
            summary=summary,
            details=details,
        )


def run_chapter() -> ExampleResult:
    return run_public_api_source_catalog_workflow()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_public_api_suite / ch166_public_api_source_catalog_workflow

        本章目标(黑盒,按使用方路径):
        - workflow 两个 demand **都可以**声明 `sources.customers`(同名 `source_id`)
        - 每个 demand 有自己的 `DemandIr.sources` 目录; live `SourceIr` **不是**同一对象
        - 图边只存 `FieldIr.source_id` / `LookupStepIr.to_source_id`
        - 全局 `LookupChunking.sized(2)` 按 id 分别 overlay 到两个目录,互不改写对方
        - 键 1..4 重叠时,alpha 必须是 `Alpha-*`,beta 必须是 `Beta-*`(证明没有串 cache / 串 loader)
        - Observer + Hook 订阅 `LOADER_CALL`(调用签名对拍);按节点拆开同名 loader 用 `Event.meta[workflow_node_id]`
        - `resources.files` 的 **file_id** 在 workflow 内必须唯一(`alpha_csv`/`beta_csv`);这与 `source_id` 可重复不是同一层身份
        - 单 demand `run` 行结果与 workflow CSV 对拍

        推荐写法:
        ```python
        from scalim.spec.ir import SourceIr
        live = SourceIr.from_catalog(demand_ir.sources, "customers")
        DemandRunRuntimeOptions(lookup_chunking={"customers": LookupChunking.sized(2)})
        ```

        SSOT:
        - `notebooks/marimo/example_public_api_suite/chapters/ch166_public_api_source_catalog_workflow.py::run_public_api_source_catalog_workflow`

        Gate:
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
    result = run_public_api_source_catalog_workflow()
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
