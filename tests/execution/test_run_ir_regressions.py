from dataclasses import replace

from scalim.execution import run_ir as run_ir_mod
from scalim.execution.output_composition import (
    AggMetricSpec,
    DerivedGroupBySpec,
    DerivedOutputTargetSpec,
    OutputCompositionSpec,
    OutputTargetSpec,
)
from scalim.execution.output_contracts import ExportLayout, OutputSpec
from tests.cases.minimal_ir import build_minimal_ir_case


def test_build_field_fingerprints_for_meta_handles_unknown_field_spec_type() -> None:
    case = build_minimal_ir_case()
    demand = replace(case.demand, fields={**case.demand.fields, "weird": object()})  # type: ignore[arg-type]
    fps = run_ir_mod._build_field_fingerprints_for_meta(demand)  # noqa: SLF001
    assert ("weird", "object", "", "") in fps


def test_select_primary_output_path_prefers_derived_primary_then_falls_back() -> None:
    spec = OutputCompositionSpec(
        targets=(
            OutputTargetSpec(
                target_id="t1",
                layout=ExportLayout(field_ids=("a",), header_names=None),
                output=OutputSpec(format="csv", path="out.csv"),
                is_primary=False,
            ),
        ),
        derived_targets=(
            DerivedOutputTargetSpec(
                target_id="d1",
                derived=DerivedGroupBySpec(
                    group_by=("g",),
                    metrics=(AggMetricSpec(out_field_id="cnt", op="count", field_id=None),),
                ),
                output_layout=ExportLayout(field_ids=("g", "cnt"), header_names=None),
                output=OutputSpec(format="csv", path="out.csv"),
                is_primary=True,
            ),
        ),
    )
    outputs = {"t1": "path_t1", "d1": "path_d1"}
    assert run_ir_mod._select_primary_output_path(outputs, spec) == "path_d1"  # noqa: SLF001

    no_primary = OutputCompositionSpec(
        targets=(
            OutputTargetSpec(
                target_id="t1",
                layout=ExportLayout(field_ids=("a",), header_names=None),
                output=OutputSpec(format="csv", path="out.csv"),
                is_primary=False,
            ),
        ),
    )
    outputs2 = {"a": "path_a", "b": "path_b"}
    assert run_ir_mod._select_primary_output_path(outputs2, no_primary) == "path_a"  # noqa: SLF001
    assert run_ir_mod._select_primary_output_path({}, no_primary) is None  # noqa: SLF001
