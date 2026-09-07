"""Cells-native marimo notebook: ch166_public_api_source_catalog_workflow.

迁移对照:
  Before: 模块级 run_public_api_source_catalog_workflow() 持全部逻辑(442 行);cells 薄壳
  After:  零件/alpha-beta 双 catalog 对照/断言全部在 cells 内
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_public_api_suite / ch166_public_api_source_catalog_workflow

        本章目标:
        - source catalog(`SourceIr.from_catalog` + field lookup steps)在编译期获得
        - 两个 demand(alpha/beta)共享同一 workflow: catalog 实例隔离 + chunk 互不泄漏
        - workflow 内 per-node `LOADER_CALL` 追踪（Observer + Hook 双视角）

        ## 主线装配过程（每个步骤一个 cell，可就地修改重跑）

        1. 零件：LOADER_CALL 追踪 / demand YAML 生成器 / catalog 读取
        2. alpha/beta demand + workflow YAML 写入
        3. `compile` → catalog 三断言（隔离 / graph id / overlay chunk size）
        4. alpha/beta solo run + workflow run → CSV 与内存行对拍
        5. 断言展开 → chapter_result

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
    import csv
    import tempfile
    from pathlib import Path
    from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple

    from scalim.dsl import yaml_dsl as api
    from scalim.events import WORKFLOW_NODE_ID_META_KEY, Event, EventType
    from scalim.hooks import BaseHook
    from scalim.ob.observer import Observer
    from scalim.spec.ir import FieldIr, LookupStepIr, SourceIr
    from scalim_misc.examples.public_api._fixtures import (
        WORKFLOW_CATALOG_ALPHA_ORDER_COUNT,
        WORKFLOW_CATALOG_BETA_ORDER_COUNT,
    )
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    ALLOWED_MODULES: FrozenSet[str] = frozenset(["scalim_misc.examples.public_api._fixtures"])
    CUSTOMER_SOURCE = "customers"
    CHUNK_SIZE = 2
    ALPHA_RUN = "alpha"
    BETA_RUN = "beta"

    return (
        ALLOWED_MODULES,
        ALPHA_RUN,
        Any,
        csv,
        BETA_RUN,
        BaseHook,
        CHUNK_SIZE,
        CUSTOMER_SOURCE,
        Dict,
        Event,
        EventType,
        FieldIr,
        FrozenSet,
        List,
        LookupStepIr,
        Mapping,
        Observer,
        Optional,
        Path,
        Sequence,
        Set,
        SourceIr,
        Tuple,
        WORKFLOW_CATALOG_ALPHA_ORDER_COUNT,
        WORKFLOW_CATALOG_BETA_ORDER_COUNT,
        WORKFLOW_NODE_ID_META_KEY,
        api,
        make_chapter_result,
        render_checks,
        tempfile,
    )


@app.cell
def _(Any, BaseHook, Dict, Event, EventType, List, Mapping, Observer, Optional, Path, Sequence, Set, Tuple, csv):
    # 零件: LOADER_CALL 追踪(含 workflow_node_id)
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

    # 零件: demand YAML 生成(单行拼接,规避 marimo 多行缩进变换)
    def demand_yaml(*, name: str, orders_loader: str, customers_loader: str, output_dir: Path, file_id: str) -> str:
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
            "\n"
        ).format(
            name=name,
            orders_loader=orders_loader,
            customers_loader=customers_loader,
            csv_dir=csv_dir,
            file_id=file_id,
        )

    def expect_chunked(n_keys: int, size: int) -> Dict[str, Any]:
        if size >= n_keys:
            return {"call_count": 1, "offsets": [None], "counts": [n_keys]}
        offsets = list(range(0, n_keys, size))
        counts = [min(size, n_keys - offset) for offset in offsets]
        return {"call_count": len(offsets), "offsets": offsets, "counts": counts}

    def call_signature(calls: Sequence[Mapping[str, Any]]) -> List[Tuple[Any, Any, Any]]:
        return [(item.get("chunk_offset"), item.get("lookup_key_count"), item.get("ids_len")) for item in calls]

    def rows_from_result(result: Any) -> List[Dict[str, Any]]:
        captured = getattr(result, "captured_rows", None)
        if captured is None:
            return []
        return list(captured.iter_row_data())

    def names_ok(rows: Sequence[Mapping[str, Any]], *, prefix: str, n_keys: int) -> bool:
        if len(rows) != n_keys:
            return False
        for row in rows:
            customer_id = row.get("customer_id")
            if row.get("customer_name") != "{}-{}".format(prefix, customer_id):
                return False
        return True

    def chunk_ok(calls: Sequence[Mapping[str, Any]], *, n_keys: int, size: int) -> bool:
        expected = expect_chunked(n_keys, size)
        offsets = [item.get("chunk_offset") for item in calls]
        counts = [item.get("lookup_key_count") for item in calls]
        return bool(len(calls) == expected["call_count"] and offsets == expected["offsets"] and counts == expected["counts"])

    def csv_names(path: Path) -> List[str]:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        return [str(row.get("customer_name") or "") for row in rows]

    def catalog_live(compilation: api.Compilation) -> Tuple[SourceIr, FieldIr, LookupStepIr]:
        demand_ir = compilation.demand_ir
        live = SourceIr.from_catalog(demand_ir.sources, CUSTOMER_SOURCE)
        field = demand_ir.fields["customer_name"]
        if not isinstance(field, FieldIr):
            raise TypeError("customer_name must be FieldIr")
        steps = field.lookup_steps or ()
        if not steps:
            raise ValueError("customer_name lookup_steps missing after compile intern")
        return live, field, steps[0]

    def write_text(path: Path, text: str) -> None:
        path.write_text(text, encoding="utf-8")

    return (
        LoaderCallHook,
        LoaderCallObserver,
        LoaderCallTrace,
        call_signature,
        catalog_live,
        chunk_ok,
        csv_names,
        demand_yaml,
        expect_chunked,
        names_ok,
        rows_from_result,
        write_text,
    )


@app.cell
def _(ALPHA_RUN, ALLOWED_MODULES, BETA_RUN, CHUNK_SIZE, CUSTOMER_SOURCE, List, Optional, Path, api, demand_yaml, tempfile, write_text):
    import atexit
    import shutil

    tmp = Path(tempfile.mkdtemp(prefix="scalim-source-catalog-wf-"))
    atexit.register(lambda: shutil.rmtree(tmp, ignore_errors=True))
    alpha_dir = tmp / "alpha_out"
    beta_dir = tmp / "beta_out"
    alpha_dir.mkdir()
    beta_dir.mkdir()
    alpha_path = tmp / "alpha.yaml"
    beta_path = tmp / "beta.yaml"
    workflow_path = tmp / "workflow.yaml"
    write_text(
        alpha_path,
        demand_yaml(
            name="catalog_alpha",
            orders_loader="load_orders_catalog_alpha",
            customers_loader="load_customers_catalog_alpha_by_ids",
            output_dir=alpha_dir,
            file_id="alpha_csv",
        ),
    )
    write_text(
        beta_path,
        demand_yaml(
            name="catalog_beta",
            orders_loader="load_orders_catalog_beta",
            customers_loader="load_customers_catalog_beta_by_ids",
            output_dir=beta_dir,
            file_id="beta_csv",
        ),
    )
    write_text(
        workflow_path,
        "workflow:\n  runs:\n    - id: {}\n      demand: alpha.yaml\n    - id: {}\n      demand: beta.yaml\n".format(ALPHA_RUN, BETA_RUN),
    )
    print("tmp dir:", tmp)

    def demand_options(*, components: Optional[List[Any]] = None) -> api.DemandRunOptions:
        return api.DemandRunOptions(
            security=api.DemandRunSecurityOptions(allowed_modules=ALLOWED_MODULES),
            runtime=api.DemandRunRuntimeOptions(
                batch_size=10,
                lookup_chunking={CUSTOMER_SOURCE: api.LookupChunking.sized(CHUNK_SIZE)},
                components=components,
            ),
            outputs=api.DemandRunOutputOptions(capture=api.CaptureRows()),
        )

    return alpha_dir, alpha_path, beta_dir, beta_path, demand_options, tmp, workflow_path


@app.cell
def _(
    LoaderCallHook,
    LoaderCallObserver,
    LoaderCallTrace,
    CHUNK_SIZE,
    CUSTOMER_SOURCE,
    api,
    alpha_path,
    beta_path,
    catalog_live,
    demand_options,
):
    # 共享 observer/hook + compile → catalog 三断言
    observer_trace = LoaderCallTrace()
    hook_trace = LoaderCallTrace()
    shared_observer = LoaderCallObserver(observer_trace)
    shared_hook = LoaderCallHook(hook_trace)
    runtime_options = demand_options(components=[shared_observer, shared_hook])

    alpha_compile = api.compile(str(alpha_path), options=runtime_options)
    beta_compile = api.compile(str(beta_path), options=runtime_options)
    alpha_live, alpha_field, alpha_step = catalog_live(alpha_compile)
    beta_live, beta_field, beta_step = catalog_live(beta_compile)
    catalogs_isolated = alpha_live is not beta_live
    graph_is_id = (
        alpha_field.source_id == CUSTOMER_SOURCE
        and beta_field.source_id == CUSTOMER_SOURCE
        and alpha_step.to_source_id == CUSTOMER_SOURCE
        and beta_step.to_source_id == CUSTOMER_SOURCE
        and not hasattr(alpha_step, "to_source")
        and not hasattr(beta_step, "to_source")
    )
    overlay_sized = alpha_live.lookup_chunk_size == CHUNK_SIZE and beta_live.lookup_chunk_size == CHUNK_SIZE
    print("isolated:", catalogs_isolated, "graph_id:", graph_is_id, "overlay:", overlay_sized)
    return (
        alpha_compile,
        alpha_field,
        alpha_live,
        alpha_step,
        beta_compile,
        beta_field,
        beta_live,
        beta_step,
        catalogs_isolated,
        graph_is_id,
        hook_trace,
        observer_trace,
        overlay_sized,
        runtime_options,
    )


@app.cell
def _(api, alpha_path, beta_path, rows_from_result, runtime_options):
    # solo run: alpha/beta 内存行
    alpha_solo = api.run(str(alpha_path), options=runtime_options)
    beta_solo = api.run(str(beta_path), options=runtime_options)
    alpha_solo_rows = rows_from_result(alpha_solo)
    beta_solo_rows = rows_from_result(beta_solo)
    alpha_solo_names = [row.get("customer_name") for row in alpha_solo_rows]
    beta_solo_names = [row.get("customer_name") for row in beta_solo_rows]
    print("alpha rows:", len(alpha_solo_rows), "beta rows:", len(beta_solo_rows))
    return alpha_solo, alpha_solo_names, alpha_solo_rows, beta_solo, beta_solo_names, beta_solo_rows


@app.cell
def _(ALPHA_RUN, BETA_RUN, api, runtime_options, workflow_path):
    from scalim.dsl.yaml_dsl import workflow_types as workflow_types_api

    api.run_workflow(
        str(workflow_path),
        options=api.WorkflowRunOptions(
            demand=runtime_options,
            patches_by_run_id={
                ALPHA_RUN: workflow_types_api.WorkflowNodePatch(),
                BETA_RUN: workflow_types_api.WorkflowNodePatch(),
            },
        ),
    )
    return workflow_types_api


@app.cell
def _(
    ALPHA_RUN,
    BETA_RUN,
    CHUNK_SIZE,
    CUSTOMER_SOURCE,
    WORKFLOW_CATALOG_ALPHA_ORDER_COUNT,
    WORKFLOW_CATALOG_BETA_ORDER_COUNT,
    alpha_dir,
    alpha_solo_names,
    alpha_solo_rows,
    beta_dir,
    beta_solo_names,
    beta_solo_rows,
    call_signature,
    chunk_ok,
    csv_names,
    hook_trace,
    names_ok,
    observer_trace,
):
    # 产物 CSV 与 solo 内存行对拍 + per-node chunk 断言
    from scalim.shortcuts.resources import outputs as resource_outputs

    alpha_csv = resource_outputs.latest_file_path(alpha_dir, file_id="alpha_csv")
    beta_csv = resource_outputs.latest_file_path(beta_dir, file_id="beta_csv")
    alpha_csv_names = csv_names(alpha_csv)
    beta_csv_names = csv_names(beta_csv)
    pair_ok = alpha_csv_names == alpha_solo_names and beta_csv_names == beta_solo_names

    alpha_obs = observer_trace.for_node_source(ALPHA_RUN, CUSTOMER_SOURCE)
    beta_obs = observer_trace.for_node_source(BETA_RUN, CUSTOMER_SOURCE)
    observer_hook_match = call_signature(observer_trace.for_source(CUSTOMER_SOURCE)) == call_signature(
        hook_trace.for_source(CUSTOMER_SOURCE)
    )
    alpha_chunked = chunk_ok(alpha_obs, n_keys=WORKFLOW_CATALOG_ALPHA_ORDER_COUNT, size=CHUNK_SIZE)
    beta_chunked = chunk_ok(beta_obs, n_keys=WORKFLOW_CATALOG_BETA_ORDER_COUNT, size=CHUNK_SIZE)
    alpha_names = names_ok(alpha_solo_rows, prefix="Alpha", n_keys=WORKFLOW_CATALOG_ALPHA_ORDER_COUNT)
    beta_names = names_ok(beta_solo_rows, prefix="Beta", n_keys=WORKFLOW_CATALOG_BETA_ORDER_COUNT)
    overlap_not_leaked = all(row.get("customer_name") == "Beta-{}".format(row.get("customer_id")) for row in beta_solo_rows) and all(
        row.get("customer_name") == "Alpha-{}".format(row.get("customer_id")) for row in alpha_solo_rows
    )

    print("pair_ok:", pair_ok, "alpha_chunk:", alpha_chunked, "beta_chunk:", beta_chunked)
    return (
        alpha_chunked,
        alpha_csv,
        alpha_csv_names,
        alpha_names,
        alpha_obs,
        beta_chunked,
        beta_csv,
        beta_csv_names,
        beta_names,
        beta_obs,
        observer_hook_match,
        overlap_not_leaked,
        pair_ok,
    )


@app.cell
def _(
    alpha_chunked,
    alpha_names,
    beta_chunked,
    beta_names,
    catalogs_isolated,
    graph_is_id,
    observer_hook_match,
    overlap_not_leaked,
    overlay_sized,
    pair_ok,
    render_checks,
):
    checks = {
        "catalog 实例隔离": catalogs_isolated,
        "graph id 引用(无 to_source)": graph_is_id,
        "overlay chunk size == 2": overlay_sized,
        "Observer/Hook 双视角一致": observer_hook_match,
        "alpha 分块黑盒一致": alpha_chunked,
        "beta 分块黑盒一致": beta_chunked,
        "alpha 行名正确": alpha_names,
        "beta 行名正确": beta_names,
        "overlap 不泄漏": overlap_not_leaked,
        "workflow CSV == solo 行": pair_ok,
    }
    render_checks(checks)
    return checks


@app.cell
def _(
    alpha_chunked,
    alpha_csv,
    alpha_csv_names,
    alpha_field,
    alpha_live,
    alpha_names,
    alpha_obs,
    alpha_solo_names,
    beta_chunked,
    beta_csv,
    beta_csv_names,
    beta_field,
    beta_live,
    beta_names,
    beta_obs,
    beta_solo_names,
    beta_step,
    call_signature,
    catalogs_isolated,
    checks,
    graph_is_id,
    make_chapter_result,
    observer_hook_match,
    overlap_not_leaked,
    overlay_sized,
    pair_ok,
):
    passed = bool(all(checks.values()))
    summary = "isolated={} graph_id={} overlay={} hook_ob={} alpha_chunk={} beta_chunk={} names_ok={}/{} overlap_ok={} pair={}".format(
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
    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "alpha_lookup_chunk_size": alpha_live.lookup_chunk_size,
            "beta_lookup_chunk_size": beta_live.lookup_chunk_size,
            "alpha_source_id": alpha_field.source_id,
            "beta_to_source_id": beta_step.to_source_id,
            "alpha_loader_calls": call_signature(alpha_obs),
            "beta_loader_calls": call_signature(beta_obs),
            "alpha_names": alpha_solo_names,
            "beta_names": beta_solo_names,
            "alpha_csv_names": alpha_csv_names,
            "beta_csv_names": beta_csv_names,
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
