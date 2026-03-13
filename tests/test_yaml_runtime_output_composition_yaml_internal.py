import pytest

from scalim.dsl.by_yaml.config_parsing.security import SecureComputeEngine
from scalim.dsl.by_yaml.runtime import output_composition_yaml as oc_yaml
from scalim.dsl.by_yaml.schema_dsl.models import (
    DemandConfig,
    OutputAggregateConfig,
    OutputAggregateMetricConfig,
    OutputContainerConfig,
    OutputExtraSheetConfig,
    OutputTargetConfig,
)
from scalim.spec.ir.demand import DemandIr
from scalim.spec.ir.fields import FieldIr
from scalim.spec.ir.sources import MainSourceIr


def _dummy_main_loader(*_args, **_kwargs):  # type: ignore[no-untyped-def]
    return []


def _make_demand_ir(*, field_name_by_id=None) -> DemandIr:  # type: ignore[no-untyped-def]
    main = MainSourceIr(source_id="orders", loader=_dummy_main_loader)
    field_irs = []
    if field_name_by_id:
        for field_id, name in field_name_by_id.items():
            field_irs.append(FieldIr(field_id=field_id, name=name, source=main))
    return DemandIr.from_irs(sources=[], fields=field_irs, main_source=main, name="demo")


def test_export_layout_for_derived_field_id_header_has_no_header_names() -> None:
    demand_ir = _make_demand_ir(field_name_by_id={"a": "A"})

    layout = oc_yaml._export_layout_for_derived(  # noqa: SLF001
        demand_ir=demand_ir,
        field_ids=["a"],
        header_fields_output_by="field_id",
    )
    assert layout.field_ids == ("a",)
    assert layout.header_names is None


def test_export_layout_for_derived_name_header_without_diffs_has_no_header_names() -> None:
    demand_ir = _make_demand_ir(field_name_by_id={"a": "a"})

    layout = oc_yaml._export_layout_for_derived(  # noqa: SLF001
        demand_ir=demand_ir,
        field_ids=["a"],
        header_fields_output_by="name",
    )
    assert layout.field_ids == ("a",)
    assert layout.header_names is None


def test_compile_where_predicate_executes_expression() -> None:
    engine = SecureComputeEngine()

    predicate = oc_yaml._compile_where_predicate(  # noqa: SLF001
        engine=engine,
        expression="channel == 'direct'",
        requires=("channel",),
    )
    assert predicate({"channel": "direct"}) is True
    assert predicate({"channel": "other"}) is False


def test_derived_output_layout_fields_includes_rank_field() -> None:
    agg = OutputAggregateConfig(
        group_by=("a",),
        metrics={"m": OutputAggregateMetricConfig(op="count")},
        rank_by="m",
        rank_field_id="r",
    )
    assert oc_yaml._derived_output_layout_fields(agg) == ("a", "m", "r")  # noqa: SLF001


def test_compile_extra_sheet_requires_workbook_path() -> None:
    with pytest.raises(ValueError, match=r"meta requires a workbook path"):
        _ = oc_yaml._compile_extra_sheet(  # noqa: SLF001
            target_id="meta",
            cfg=OutputExtraSheetConfig(),
            default_sheet="__meta__",
            default_workbook_container=None,
        )


def test_first_workbook_container_skips_none_container() -> None:
    outputs = (
        OutputTargetConfig(name="a", container=None),
        OutputTargetConfig(name="b", container=OutputContainerConfig(type="workbook", path="./out.xlsx", sheet="S")),
    )

    container = oc_yaml._first_workbook_container(outputs)  # noqa: SLF001
    assert container is not None
    assert container.type == "workbook"
    assert container.path == "./out.xlsx"


def test_compile_output_composition_meta_audit_requires_outputs() -> None:
    config = DemandConfig(meta=OutputExtraSheetConfig())

    with pytest.raises(ValueError, match=r"meta/audit requires outputs"):
        _ = oc_yaml.compile_output_composition_from_yaml(config, _make_demand_ir())


def test_compile_output_composition_returns_none_when_no_outputs() -> None:
    assert oc_yaml.compile_output_composition_from_yaml(DemandConfig(), _make_demand_ir()) is None


def test_compile_output_composition_meta_output_name_is_reserved() -> None:
    config = DemandConfig(
        outputs=(
            OutputTargetConfig(
                name="meta",
                container=OutputContainerConfig(type="workbook", path="./out.xlsx", sheet="S"),
                fields=("a",),
            ),
        ),
        meta=OutputExtraSheetConfig(),
    )

    with pytest.raises(ValueError, match=r"cannot be 'meta'"):
        _ = oc_yaml.compile_output_composition_from_yaml(config, _make_demand_ir())


def test_compile_output_composition_audit_output_name_is_reserved() -> None:
    config = DemandConfig(
        outputs=(
            OutputTargetConfig(
                name="audit",
                container=OutputContainerConfig(type="workbook", path="./out.xlsx", sheet="S"),
                fields=("a",),
            ),
        ),
        audit=OutputExtraSheetConfig(),
    )

    with pytest.raises(ValueError, match=r"cannot be 'audit'"):
        _ = oc_yaml.compile_output_composition_from_yaml(config, _make_demand_ir())


def test_compile_output_composition_requires_container() -> None:
    config = DemandConfig(outputs=(OutputTargetConfig(name="detail", container=None, fields=("a",)),))

    with pytest.raises(ValueError, match=r"outputs\.detail missing container"):
        _ = oc_yaml.compile_output_composition_from_yaml(config, _make_demand_ir())
