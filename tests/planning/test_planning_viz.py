# region imports

import json
from pathlib import Path

import pytest

from scalim.dsl.yaml_dsl.runtime.introspection import build_viz_observer
from scalim.dsl.yaml_dsl.runtime.errors import ScalimAllowlistRequiredError
from scalim.events._events import DiagnosticWarningEvent, ErrorEvent, LoaderCallEvent, PipelineEndEvent, PipelineStartEvent
from scalim.ob.observability import Observability
from scalim.ob.presets.viz import VizObserver, VizObserverConfig
from scalim.planning.plan import ExecutionPlan, PlanMetadata, Stage
from scalim.planning.viz import _viz_add_node, _viz_add_source_edges, _viz_collect_fields
from scalim.spec.ir import CallBySpecIr, CallByValueIr, DerivedFieldIr, FieldIr, LoaderIr, RuntimeHandleIdIr
from scalim.spec.ir import LookupStepIr
from scalim.spec.ir import KeyIr, MainSourceIr, SourceIr
from tests.support.pathing import fixtures_dir
from tests.support.event_envelope import event_envelope

# endregion


def _build_plan_with_stages() -> ExecutionPlan:
    main_source = MainSourceIr(source_id="orders", loader_ref=RuntimeHandleIdIr(handle_id="orders.main_loader"))
    _ = SourceIr(
        source_id="customers",
        key=KeyIr("customer_id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="customers.loader")),
    )

    field_order_id = FieldIr(field_id="order_id", name="订单ID", source=main_source, is_primary=True)
    field_customer_id = FieldIr(field_id="customer_id", name="客户ID", source=main_source)
    derived_profit = DerivedFieldIr(
        field_id="profit",
        name="利润",
        dependencies=("order_id", "customer_id"),
        call_by=CallBySpecIr(
            reference=RuntimeHandleIdIr(handle_id="derived.profit"),
            args=(
                CallByValueIr(kind="field", value="order_id"),
                CallByValueIr(kind="field", value="customer_id"),
            ),
            field_names=("order_id", "customer_id"),
        ),
    )

    metadata = PlanMetadata(total_fields=3, total_sources=2, total_loaders=2)
    stages = [
        Stage(stage_id="stage0", field_keys=["order_id", "customer_id"], level=0),
        Stage(stage_id="stage1", field_keys=["profit"], level=1),
    ]

    return ExecutionPlan(
        operators=(),
        primary_field="order_id",
        key_fields=frozenset(["order_id"]),
        preload_sources=(),
        field_order=["order_id", "customer_id", "profit"],
        loader_sequence=[],
        ref_loader_sequence=[],
        stages=stages,
        metadata=metadata,
        field_specs={
            "order_id": field_order_id,
            "customer_id": field_customer_id,
            "profit": derived_profit,
        },
        target_fields=["profit"],
        field_dependencies={"profit": ("order_id", "customer_id")},
    )


def _build_simple_plan() -> ExecutionPlan:
    main_source = MainSourceIr(source_id="orders", loader_ref=RuntimeHandleIdIr(handle_id="orders.main_loader"))
    field_order_id = FieldIr(field_id="order_id", name="Order ID", source=main_source, is_primary=True)
    metadata = PlanMetadata(total_fields=1, total_sources=1, total_loaders=1)
    stages = [Stage(stage_id="stage0", field_keys=["order_id"], level=0)]
    return ExecutionPlan(
        operators=(),
        primary_field="order_id",
        key_fields=frozenset(["order_id"]),
        preload_sources=(),
        field_order=["order_id"],
        loader_sequence=[],
        ref_loader_sequence=[],
        stages=stages,
        metadata=metadata,
        field_specs={"order_id": field_order_id},
        target_fields=["order_id"],
        field_dependencies={},
    )


def _write_yaml(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def test_viz_graph_snapshot_includes_nodes_and_stages() -> None:
    plan = _build_plan_with_stages()
    snapshot = plan.to_viz_graph_snapshot()

    node_id_list = [node["id"] for node in snapshot["nodes"]]
    assert node_id_list == sorted(node_id_list)

    node_ids = {node["id"] for node in snapshot["nodes"]}
    assert "field:order_id" in node_ids
    assert "field:customer_id" in node_ids
    assert "field:profit" in node_ids
    assert "source:orders" in node_ids
    assert "loader:orders" in node_ids
    assert snapshot["meta"]["schema_version"] == "vizgraph/v1"
    assert snapshot["stages"]
    assert snapshot["stages"][0]["stage_id"] == "stage0"

    edge_triplets = [(edge.get("source", ""), edge.get("target", ""), edge.get("type", "")) for edge in snapshot["edges"]]
    assert edge_triplets == sorted(edge_triplets)
    for idx, edge in enumerate(snapshot["edges"]):
        assert edge["id"].startswith("e{}:".format(idx))


def test_viz_graph_snapshot_skips_optional_node_groups() -> None:
    plan = _build_simple_plan()
    snapshot = plan.to_viz_graph_snapshot(
        include_stage_nodes=False,
        include_loader_nodes=False,
        include_source_nodes=False,
    )

    node_ids = {node["id"] for node in snapshot["nodes"]}
    assert "field:order_id" in node_ids
    assert not any(node_id.startswith("stage:") for node_id in node_ids)
    assert not any(node_id.startswith("loader:") for node_id in node_ids)
    assert not any(node_id.startswith("source:") for node_id in node_ids)

    edge_types = {edge["type"] for edge in snapshot["edges"]}
    assert "in_stage" not in edge_types
    assert "loads_from" not in edge_types


def test_viz_observer_outputs_jsonl_sample(tmp_path: Path) -> None:
    output_path = tmp_path / "viz.jsonl"
    config = VizObserverConfig(
        output_path=str(output_path),
        payload_policy="sample",
        sample_size=2,
    )
    observer = VizObserver(config=config, snapshot={"meta": {"target_fields": ["profit"]}})

    observer.on_pipeline_start(event_envelope(PipelineStartEvent(targets=["profit"], batch_size=100)))
    observer.on_loader_call(
        event_envelope(
            LoaderCallEvent(
                loader_name="orders",
                params={},
                result=[{"order_id": 1}, {"order_id": 2}, {"order_id": 3}],
                duration=0.05,
            )
        )
    )
    observer.on_error(event_envelope(ErrorEvent(ValueError("boom"), {"field_key": "profit", "row_id": 1})))
    observer.on_diagnostic_warning(
        event_envelope(
            DiagnosticWarningEvent(
                message="float lookup key",
                source_id="orders",
                field_id="profit",
                lookup_key="1001.0",
                row_id=1,
            )
        )
    )
    observer.on_pipeline_end(event_envelope(PipelineEndEvent(total_batches=1, total_duration=0.2)))

    lines = output_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 2
    events = [json.loads(line) for line in lines]

    event_types = {evt["event_type"] for evt in events}
    assert "run_started" in event_types
    assert "loader_called" in event_types
    assert "error" in event_types
    assert "diagnostic_warning" in event_types
    assert "run_finished" in event_types
    assert {evt.get("schema_version") for evt in events} == {"vizevent/v1"}

    loader_events = [evt for evt in events if evt["event_type"] == "loader_called"]
    assert loader_events
    payload = loader_events[0]["payload"]
    assert payload.get("sample_size") == 2


def test_viz_observer_writes_snapshot_and_events_to_output_dir(tmp_path: Path) -> None:
    config = VizObserverConfig(
        output_dir=str(tmp_path),
        payload_policy="summary",
    )
    observer = VizObserver(config=config, snapshot={"meta": {"target_fields": ["profit"]}})

    observer.on_pipeline_start(event_envelope(PipelineStartEvent(targets=["profit"], batch_size=10)))
    observer.on_pipeline_end(event_envelope(PipelineEndEvent(total_batches=1, total_duration=0.1)))

    base_dir = tmp_path / "scalim-viz"
    run_dirs = [item for item in base_dir.iterdir() if item.is_dir()]
    assert run_dirs
    run_dir = run_dirs[0]
    snapshot_path = run_dir / "viz_snapshot.json"
    events_path = run_dir / "viz_events.jsonl"
    assert snapshot_path.exists()
    assert events_path.exists()


def test_viz_observer_emits_error_and_warning_node_refs(tmp_path: Path) -> None:
    output_path = tmp_path / "viz.jsonl"
    config = VizObserverConfig(
        output_path=str(output_path),
        payload_policy="summary",
        sample_size=1,
    )
    observer = VizObserver(config=config, snapshot={"meta": {"target_fields": ["profit"]}})

    observer.on_pipeline_start(event_envelope(PipelineStartEvent(targets=["profit"], batch_size=10)))
    observer.on_error(event_envelope(ErrorEvent(ValueError("boom"), {"field_key": "profit", "row_id": 1})))
    observer.on_error(event_envelope(ErrorEvent(RuntimeError("oops"), {"loader_name": "orders"})))
    observer.on_error(event_envelope(ErrorEvent(RuntimeError("oops2"), {"source_id": "orders"})))
    observer.on_error(event_envelope(ErrorEvent(RuntimeError("oops3"), {})))
    observer.on_diagnostic_warning(
        event_envelope(
            DiagnosticWarningEvent(
                message="float lookup key",
                source_id="orders",
                field_id="profit",
                lookup_key="1001.0",
                row_id=1,
            )
        )
    )
    observer.on_pipeline_end(event_envelope(PipelineEndEvent(total_batches=1, total_duration=0.1)))

    events = [json.loads(line) for line in output_path.read_text(encoding="utf-8").strip().splitlines()]
    error_events = [evt for evt in events if evt["event_type"] == "error"]
    warning_events = [evt for evt in events if evt["event_type"] == "diagnostic_warning"]
    assert len(error_events) == 4
    assert warning_events

    node_refs = {evt["node_ref"]["type"] for evt in error_events}
    assert {"field", "loader", "source", "pipeline"} <= node_refs


def test_parse_viz_config_enabled_and_infer() -> None:
    plan = _build_simple_plan()
    viz_config = VizObserverConfig(use_default_output_dir=True, payload_policy="summary", sample_size=3, run_name="demo", env="test")
    assert viz_config.is_enabled() is True

    observer_with_plan = VizObserver.from_plan(plan, viz_config)
    assert observer_with_plan.snapshot is not None


def test_runtime_viz_hook_creation_and_registration() -> None:
    plan = _build_simple_plan()
    viz_config = VizObserverConfig(use_default_output_dir=True)
    observer_with_plan = VizObserver.from_plan(plan, viz_config)
    assert observer_with_plan.snapshot is not None

    observability_facade = Observability(observers=[])
    observability_facade.register(observer_with_plan)
    manager = observability_facade.build_manager()
    assert any(isinstance(obs, VizObserver) for obs in manager.observers)


def test_build_viz_observer_allowlist_and_targets(tmp_path: Path) -> None:
    with pytest.raises(ScalimAllowlistRequiredError):
        build_viz_observer(str(tmp_path / "missing.yaml"), allowed_modules=frozenset())

    try:
        __import__("scalim_misc.example_report_ir")
    except Exception as exc:
        pytest.skip("demo yaml fixtures unavailable in this environment: {}".format(exc))

    allowed_modules = frozenset(["scalim_misc.example_report_ir"])
    fixture_path = fixtures_dir() / "order_report.yaml"
    observer = build_viz_observer(str(fixture_path), allowed_modules=allowed_modules)
    assert isinstance(observer, VizObserver)
    assert observer.snapshot is not None

    minimal_yaml = """
name: mini
main_source:
  source_id: orders
  loader: "scalim_misc.example_report_ir:DAL.paged_get_order_list"
  fields:
    order_id:
      extract: order_id
      name: Order ID
sources: {}
"""
    minimal_path = tmp_path / "mini.yaml"
    _write_yaml(minimal_path, minimal_yaml.strip() + "\n")
    observer = build_viz_observer(str(minimal_path), allowed_modules=allowed_modules)
    assert isinstance(observer, VizObserver)
    assert observer.snapshot is not None


def test_viz_plan_helpers_cover_branches() -> None:
    nodes = []
    node_ids = set()

    def add_node(node_id: str, node_type: str, data: dict) -> None:
        _viz_add_node(nodes, node_ids, node_id, node_type, data)

    add_node("field:order_id", "field", {"label": "Order ID"})
    add_node("field:order_id", "field", {"label": "Order ID"})
    assert len(nodes) == 1

    class DummyField:
        pass

    _viz_collect_fields({"unknown": DummyField()}, add_node)
    assert any(node["id"] == "field:unknown" for node in nodes)

    main_source = MainSourceIr(source_id="orders", loader_ref=RuntimeHandleIdIr(handle_id="orders.main_loader"))
    ref_source = SourceIr(
        source_id="customers",
        key=KeyIr("customer_id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="customers.loader")),
    )
    lookup_step = LookupStepIr(from_field="customer_id", to_source=ref_source)
    ref_field = FieldIr(
        field_id="customer_name",
        name="Customer Name",
        source=main_source,
        lookup_steps=(lookup_step,),
    )
    edges = []

    def add_edge(source: str, target: str, edge_type: str) -> None:
        edges.append((source, target, edge_type))

    _viz_add_source_edges(
        {"orders": ["customer_name"]},
        {"customer_name": ref_field},
        include_source_nodes=True,
        include_loader_nodes=False,
        add_edge=add_edge,
    )
    assert ("source:orders", "field:customer_name", "ref_lookup") in edges


def test_viz_observer_close_is_noop_without_emitter() -> None:
    observer = VizObserver()
    observer.close()
