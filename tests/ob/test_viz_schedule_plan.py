from pathlib import Path

from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunSecurityOptions, compile
from scalim.planning import PlanBuilder
from scalim.planning.viz_schedule import _build_layers, _build_ref_deps


def _write_yaml(tmp_path: Path, text: str) -> Path:
    yaml_path = tmp_path / "viz_schedule.yaml"
    yaml_path.write_text(text.strip() + "\n", encoding="utf-8")
    return yaml_path


def test_viz_schedule_plan_from_yaml_layers_and_barrier(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: viz_schedule_demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: id
    pay_id:
      extract: pay_id
sources:
  pays:
    loader: tests.fixtures.mock_loaders.mock_loader
    key: pay_id
    params:
      pay_ids: {$keys: {as: set}}
    fields:
      country_id:
        extract: country_id
        relation:
          steps:
            - from: orders.pay_id
              to: pays.pay_id
      pay_method:
        extract: method
        relation:
          steps:
            - from: orders.pay_id
              to: pays.pay_id
  countries:
    loader: tests.fixtures.mock_loaders.mock_loader
    key: country_id
    params:
      rows: {$rows: {cache_mode: batch}}
    fields:
      country_name:
        extract: name
        relation:
          steps:
            - from: orders.pay_id
              to: pays.pay_id
            - from: pays.country_id
              to: countries.country_id
""",
    )

    compilation = compile(
        str(yaml_path),
        options=DemandRunOptions(security=DemandRunSecurityOptions(allowed_modules=frozenset(["tests.fixtures.mock_loaders"]))),
    )
    plan = PlanBuilder(compilation.demand_ir).build(targets=["country_name", "pay_method", "country_id"])

    schedule_plan = plan.to_viz_schedule_plan()
    assert schedule_plan["targets"] == ["country_name", "pay_method", "country_id"]

    load_ref = schedule_plan["load_ref"]
    assert load_ref["op_count"] == 3
    assert load_ref["layer_count"] == 2

    layer0 = load_ref["layers"][0]
    assert layer0["rows_binding_barrier"] is False
    assert layer0["task_group_count"] == 1
    assert layer0["tasks"][0]["chain"] == ["pays"]
    assert layer0["tasks"][0]["rows_binding"] is False
    assert set(layer0["tasks"][0]["fields"]) == {"country_id", "pay_method"}

    layer1 = load_ref["layers"][1]
    assert layer1["rows_binding_barrier"] is True
    assert layer1["task_group_count"] == 1
    assert layer1["tasks"][0]["chain"] == ["pays", "countries"]
    assert layer1["tasks"][0]["rows_binding"] is True
    assert layer1["tasks"][0]["fields"] == ["country_name"]


def test_viz_schedule_layers_fallback_for_cycles() -> None:
    layers = _build_layers(["a", "b"], deps={"a": ("b",), "b": ("a",)})
    assert layers == [["a", "b"]]


def test_viz_schedule_ref_deps_accepts_nonempty_str_dep() -> None:
    from types import SimpleNamespace

    plan = SimpleNamespace(ref_loader_sequence=[(None, [("ref_a", "ref_b")])])
    assert _build_ref_deps(plan) == {"ref_a": ("ref_b",)}
