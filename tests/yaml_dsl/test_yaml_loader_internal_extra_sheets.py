import pytest

from scalim.dsl.yaml_dsl import (
    DemandRunOptions,
    DemandRunOutputOptions,
    DemandRunSecurityOptions,
    OutputExtraSheetOverride,
    OutputExtrasOverride,
    RunOverrides,
    compile,
)
from scalim.dsl.yaml_dsl._internal import resource_override as resource_override_mod
from scalim.dsl.yaml_dsl._internal.config_parsing.loader import YamlDemandLoader
from scalim.dsl.yaml_dsl._internal.config_parsing.models import RawDemand
from scalim.dsl.yaml_dsl._internal.config_parsing.yaml_load import ScalimYamlValidationError
from scalim.dsl.yaml_dsl.runtime import compiler as compiler_mod
from scalim.dsl.yaml_dsl.schema_dsl.models import DemandConfig
from scalim.workflow.errors import ScalimWorkflowConfigError


def test_loader_parse_config_ignores_failure_policy_key() -> None:
    loader = YamlDemandLoader()

    raw = RawDemand.from_raw(
        {
            "name": "demo",
            "main_source": {"source_id": "orders", "loader": "tests.fixtures.mock_loaders.mock_loader"},
            "failure_policy": "bad",
            "sources": {},
        }
    )

    config = loader._parse_config(raw)  # type: ignore[attr-defined]
    assert config.failure_policy == "all_fail"


def test_yaml_validation_rejects_meta_and_audit_keys_with_migration_hint(tmp_path) -> None:  # type: ignore[no-untyped-def]
    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(
        (
            """
name: demo

main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    id: {extract: id}

resources:
  books:
    report:
      xlsx_file:
        path: ./out

outputs:
  - name: detail
    to: {book: report, sheet: S}
    fields: [id]

meta: true
audit: true
"""
        ).lstrip(),
        encoding="utf-8",
    )

    loader = YamlDemandLoader()
    with pytest.raises(ScalimYamlValidationError) as exc_info:
        _ = loader.load(str(yaml_path))

    errs = list(exc_info.value.errors)
    assert any(e.path == "meta" and "output extras boundary" in e.message for e in errs)
    assert any(e.path == "audit" and "output extras boundary" in e.message for e in errs)


def test_runtime_overrides_output_extras_compile_to_output_composition(tmp_path) -> None:  # type: ignore[no-untyped-def]
    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(
        (
            """
name: demo

main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    id: {extract: id}

resources:
  books:
    report:
      xlsx_file:
        path: ./out

outputs:
  - name: detail
    to: {book: report, sheet: S}
    fields: [id]
"""
        ).lstrip(),
        encoding="utf-8",
    )

    compilation = compile(
        str(yaml_path),
        options=DemandRunOptions(
            security=DemandRunSecurityOptions(allowed_modules=frozenset(["tests.fixtures.mock_loaders"])),
            outputs=DemandRunOutputOptions(
                overrides=RunOverrides(
                    output_extras=OutputExtrasOverride(
                        meta=True,
                        audit=OutputExtraSheetOverride(sheet="__audit__"),
                    )
                )
            ),
        ),
    )
    assert compilation.request.output_composition is not None
    assert compilation.request.output_composition.meta_sheet is not None
    assert compilation.request.output_composition.audit_sheet is not None
    assert compilation.request.output_composition.targets
    detail = next(t for t in compilation.request.output_composition.targets if t.target_id == "detail")
    assert compilation.request.output_composition.meta_sheet.output.path == detail.output.path
    assert compilation.request.output_composition.audit_sheet.sheet_name == "__audit__"


def test_run_overrides_output_extras_legacy_dict_fail_fast() -> None:
    with pytest.raises(TypeError, match=r"RunOverrides\.output_extras=dict"):
        _ = RunOverrides(output_extras={"meta": True})  # type: ignore[arg-type]


def test_run_overrides_output_extras_wrong_type_fail_fast() -> None:
    with pytest.raises(TypeError, match=r"RunOverrides\.output_extras must be an OutputExtrasOverride"):
        _ = RunOverrides(output_extras=object())  # type: ignore[arg-type]


def test_output_extras_override_rejects_invalid_item_type() -> None:
    with pytest.raises(TypeError, match=r"meta must be a boolean or an OutputExtraSheetOverride"):
        _ = OutputExtrasOverride(meta=object())  # type: ignore[arg-type]


def test_runtime_compiler_parse_output_extra_sheet_override_error_branches() -> None:
    assert resource_override_mod.parse_output_extra_sheet_override(False, path="p") is None  # noqa: SLF001

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = resource_override_mod.parse_output_extra_sheet_override(1, path="p")  # noqa: SLF001
    assert exc_info.value.path == "p"

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = resource_override_mod.parse_output_extra_sheet_override(OutputExtraSheetOverride(path=1), path="p")  # noqa: SLF001
    assert exc_info.value.path == "p.path"

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = resource_override_mod.parse_output_extra_sheet_override(
            OutputExtraSheetOverride(allow_formulas="nope"),
            path="p",
        )  # noqa: SLF001
    assert exc_info.value.path == "p.allow_formulas"


def test_runtime_compiler_apply_output_extras_overrides_rejects_invalid_extras_type() -> None:
    overrides = RunOverrides()
    object.__setattr__(overrides, "output_extras", object())
    options = DemandRunOptions(
        security=DemandRunSecurityOptions(allowed_modules=frozenset(["tests.fixtures.mock_loaders"])),
        outputs=DemandRunOutputOptions(overrides=overrides),
    )

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = compiler_mod._apply_output_extras_overrides(DemandConfig(), options=options)  # noqa: SLF001
    assert exc_info.value.path == "overrides.output_extras"
