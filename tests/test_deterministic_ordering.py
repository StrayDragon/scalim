import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

from scalim.dsl.by_yaml.runtime.conversion import ConfigToIRConverter
from scalim.dsl.by_yaml.schema_dsl.models import BindConfig, BindKeysConfig
from scalim.planning import PlanBuilder
from scalim.spec.ir.binding import LoaderCallContextIr, build_stable_lookup_key_list
from scalim.spec.ir.demand import DemandIr
from scalim.spec.ir.fields import DerivedFieldIr, FieldIr
from scalim.spec.ir.sources import MainSourceIr
from scalim.utils.graph import topological_sort


def test_topological_sort_empty_returns_empty() -> None:
    assert topological_sort([], lambda _x: []) == []


def test_topological_sort_stable_tie_break_for_same_layer_nodes() -> None:
    deps = {"a": [], "b": [], "c": ["a", "b"]}
    assert topological_sort(["b", "a", "c"], lambda x: deps.get(x, [])) == ["a", "b", "c"]


def test_topological_sort_non_string_nodes_use_stable_tie_break() -> None:
    result = topological_sort([2, 1, 3], lambda _x: [])
    assert result == [1, 2, 3]


def test_stable_lookup_keys_list_sorts_tuple_keys() -> None:
    assert build_stable_lookup_key_list({("b", 2), ("a", 1)}) == [("a", 1), ("b", 2)]


def test_yaml_params_builder_use_keys_as_list_prefers_lookup_keys_list_when_present() -> None:
    converter = ConfigToIRConverter(allow_unsafe_resolver=True)
    bind_config = BindConfig(use_keys=BindKeysConfig(param="ids", as_="list"))
    builder = converter._create_params_builder(bind_config)

    ctx = LoaderCallContextIr(
        lookup_keys={1, 2},
        lookup_keys_list=[2, 1],
    )
    _args, kwargs = builder(ctx)
    assert kwargs["ids"] == [2, 1]


def test_yaml_params_builder_use_keys_as_list_stable_sorts_lookup_keys_when_list_missing() -> None:
    converter = ConfigToIRConverter(allow_unsafe_resolver=True)
    bind_config = BindConfig(use_keys=BindKeysConfig(param="ids", as_="list"))
    builder = converter._create_params_builder(bind_config)

    ctx = LoaderCallContextIr(
        lookup_keys={3, 1, 2},
        lookup_keys_list=None,
    )
    _args, kwargs = builder(ctx)
    assert kwargs["ids"] == [1, 2, 3]


def test_yaml_params_builder_use_keys_as_list_uses_batch_row_nth_for_non_ref_loader() -> None:
    converter = ConfigToIRConverter(allow_unsafe_resolver=True)
    bind_config = BindConfig(use_keys=BindKeysConfig(param="row_ids", as_="list"))
    builder = converter._create_params_builder(bind_config)

    ctx = LoaderCallContextIr(batch_row_nth=[2, 1])
    _args, kwargs = builder(ctx)
    assert kwargs["row_ids"] == [2, 1]


def test_plan_builder_field_specs_and_dependencies_follow_field_order() -> None:
    main_source = MainSourceIr(source_id="main", loader=lambda: [])
    id_field = FieldIr(field_id="id", name="ID", source=main_source, is_primary=True)
    a_field = DerivedFieldIr(field_id="a", name="A", dependencies=("id",), calculator=lambda id: id)
    b_field = DerivedFieldIr(field_id="b", name="B", dependencies=("id",), calculator=lambda id: id)

    demand = DemandIr.from_irs(sources=[], fields=[id_field, a_field, b_field], main_source=main_source)
    plan = PlanBuilder(demand).build(targets=["a", "b"])

    assert list(plan.field_specs.keys()) == plan.field_order
    assert list(plan.field_dependencies.keys()) == plan.field_order


def _run_hashseed_snippet(seed: str, snippet: str) -> Any:
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = str(seed)
    env["PYTHONPATH"] = str(root)
    dedented = textwrap.dedent(snippet).strip()
    out = subprocess.check_output([sys.executable, "-c", dedented], env=env, cwd=str(root), text=True)
    return json.loads(out)


def test_plan_order_is_hashseed_stable() -> None:
    snippet = """
import json
from scalim.planning import PlanBuilder
from scalim.spec.ir.demand import DemandIr
from scalim.spec.ir.fields import DerivedFieldIr, FieldIr
from scalim.spec.ir.sources import MainSourceIr

main = MainSourceIr(source_id="main", loader=lambda: [])
id_field = FieldIr(field_id="id", name="ID", source=main, is_primary=True)
a_field = DerivedFieldIr(field_id="a", name="A", dependencies=("id",), calculator=lambda id: id)
b_field = DerivedFieldIr(field_id="b", name="B", dependencies=("id",), calculator=lambda id: id)

demand = DemandIr.from_irs(sources=[], fields=[id_field, a_field, b_field], main_source=main)
plan = PlanBuilder(demand).build(targets=["a", "b"])

compute_fields = []
for op in plan.operators:
    if getattr(op, "operator_type", None) == "compute":
        compute_fields.append(op.field_spec.field_id)

print(json.dumps({"field_order": plan.field_order, "compute_fields": compute_fields}))
"""
    result_a = _run_hashseed_snippet("1", snippet)
    result_b = _run_hashseed_snippet("2", snippet)
    assert result_a == result_b


def test_keys_list_is_hashseed_stable() -> None:
    snippet = """
import json
from scalim.dsl.by_yaml.runtime.conversion import ConfigToIRConverter
from scalim.dsl.by_yaml.schema_dsl.models import BindConfig, BindKeysConfig
from scalim.spec.ir.binding import LoaderCallContextIr

converter = ConfigToIRConverter(allow_unsafe_resolver=True)
bind_config = BindConfig(use_keys=BindKeysConfig(param="ids", as_="list"))
builder = converter._create_params_builder(bind_config)

ctx = LoaderCallContextIr(lookup_keys=set([(2, "b"), (1, "a")]))
_args, kwargs = builder(ctx)
print(json.dumps(kwargs["ids"]))
"""
    result_a = _run_hashseed_snippet("1", snippet)
    result_b = _run_hashseed_snippet("2", snippet)
    assert result_a == result_b
