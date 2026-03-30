import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest

from scalim.dsl.by_yaml.params_template import ScalimParamsTemplateRenderError, compile_params_template
from scalim.dsl.by_yaml.runtime.conversion import ConfigToIRConverter
from scalim.dsl.by_yaml.runtime.errors import ScalimConversionError
from scalim.dsl.by_yaml.schema_dsl.models import LookupCastConfig
from scalim.planning import PlanBuilder
from scalim.spec.ir.binding import LoaderCallContextIr, BindingIr, _is_valid_binding_key, _restore_bindings, build_stable_lookup_key_list
from scalim.spec.ir import DemandIr
from scalim.spec.ir import DerivedFieldIr, FieldIr
from scalim.spec.ir import MainSourceIr
from scalim._internal.utils.graph import topological_sort
from tests.support.pathing import repo_root as _repo_root


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
    template = compile_params_template({"ids": {"$keys": {"as": "list"}}}, path="sources.s1.params", resolve_runtime=False)

    ctx = LoaderCallContextIr(
        is_ref_loader=True,
        lookup_keys={1, 2},
        lookup_keys_list=[2, 1],
    )
    kwargs = template.render_kwargs(ctx, path="sources.s1.params")
    assert kwargs["ids"] == [2, 1]


def test_yaml_params_builder_use_keys_as_list_stable_sorts_lookup_keys_when_list_missing() -> None:
    template = compile_params_template({"ids": {"$keys": {"as": "list"}}}, path="sources.s1.params", resolve_runtime=False)

    ctx = LoaderCallContextIr(
        is_ref_loader=True,
        lookup_keys={3, 1, 2},
        lookup_keys_list=None,
    )
    kwargs = template.render_kwargs(ctx, path="sources.s1.params")
    assert kwargs["ids"] == [1, 2, 3]


def test_yaml_params_builder_use_keys_as_list_uses_batch_row_nth_for_non_ref_loader() -> None:
    template = compile_params_template({"row_ids": {"$keys": {"as": "list"}}}, path="sources.s1.params", resolve_runtime=False)
    ctx = LoaderCallContextIr(batch_row_nth=[2, 1])
    with pytest.raises(ScalimParamsTemplateRenderError, match="only valid in ref loader call contexts"):
        _ = template.render_kwargs(ctx, path="sources.s1.params")


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
    root = _repo_root()
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = str(seed)
    env["PYTHONPATH"] = str(root)
    dedented = textwrap.dedent(snippet).strip()
    out = subprocess.check_output(
        [sys.executable, "-c", dedented],
        env=env,
        cwd=str(root),
        text=True,
        timeout=20.0,
    )
    return json.loads(out)


def test_plan_order_is_hashseed_stable() -> None:
    snippet = """
import json
from scalim.planning import PlanBuilder
from scalim.spec.ir import DemandIr
from scalim.spec.ir import DerivedFieldIr, FieldIr
from scalim.spec.ir import MainSourceIr

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
from scalim.dsl.by_yaml.params_template import compile_params_template
from scalim.spec.ir.binding import LoaderCallContextIr

template = compile_params_template({"ids": {"$keys": {"as": "list"}}}, path="sources.s1.params", resolve_runtime=False)

ctx = LoaderCallContextIr(is_ref_loader=True, lookup_keys=set([(2, "b"), (1, "a")]))
kwargs = template.render_kwargs(ctx, path="sources.s1.params")
print(json.dumps(kwargs["ids"]))
"""
    result_a = _run_hashseed_snippet("1", snippet)
    result_b = _run_hashseed_snippet("2", snippet)
    assert result_a == result_b


def test_binding_key_validation_and_restore_guards() -> None:
    assert _is_valid_binding_key("id") is True
    assert _is_valid_binding_key(("region", "institution")) is True
    assert _is_valid_binding_key(123) is False
    assert _is_valid_binding_key(("region", 1)) is False

    assert _restore_bindings([]) is None


def test_restore_bindings_rejects_invalid_state_entries() -> None:
    valid_binding = BindingIr(key_field="id", params_builder=lambda _ctx: ((), {}))

    with pytest.raises(TypeError) as excinfo:
        _restore_bindings({1: valid_binding})
    assert "Invalid binding key" in str(excinfo.value)

    with pytest.raises(TypeError) as excinfo:
        _restore_bindings({"id": object()})
    assert "Invalid binding value" in str(excinfo.value)


def test_lookup_cast_requires_initialized_registry() -> None:
    converter = ConfigToIRConverter.from_allowlist(allowed_modules=frozenset(["tests.fixtures.mock_loaders"]))
    converter._lookup_casts = None

    with pytest.raises(ScalimConversionError) as excinfo:
        converter._get_lookup_cast_fn(LookupCastConfig(name="auto", sep=None), is_multi=False)
    assert "Lookup cast registry is not initialized" in str(excinfo.value)
