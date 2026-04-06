import pytest

from scalim.dsl.by_yaml import OutputExtraSheetOverride, OutputExtrasOverride, RunOptions, RunOverrides, compile
from scalim.dsl.by_yaml._internal.config_parsing.loader import YamlDemandLoader
from scalim.dsl.by_yaml._internal.config_parsing.models import RawDemand
from scalim.dsl.by_yaml._internal.config_parsing.yaml_load import ScalimYamlValidationError
from scalim.dsl.by_yaml.runtime import compiler as compiler_mod
from scalim.dsl.by_yaml.schema_dsl.models import DemandConfig


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
      kind: xlsx_file
      path: ./out.xlsx
      write_defaults: {mode: sheet}

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
      kind: xlsx_file
      path: ./out.xlsx
      write_defaults: {mode: sheet}

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
        options=RunOptions(
            allowed_modules=frozenset(["tests.fixtures.mock_loaders"]),
            overrides=RunOverrides(
                output_extras=OutputExtrasOverride(
                    meta=True,
                    audit=OutputExtraSheetOverride(sheet="__audit__"),
                )
            ),
        ),
    )
    assert compilation.request.output_composition is not None
    assert compilation.request.output_composition.meta_sheet is not None
    assert compilation.request.output_composition.audit_sheet is not None
    assert compilation.request.output_composition.meta_sheet.output.path == str(tmp_path / "out.xlsx")
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
    assert compiler_mod._parse_output_extra_sheet_override(False, path="p") is None  # noqa: SLF001

    with pytest.raises(TypeError, match=r"p must be a boolean or an OutputExtraSheetOverride"):
        _ = compiler_mod._parse_output_extra_sheet_override(1, path="p")  # noqa: SLF001

    with pytest.raises(TypeError, match=r"p\.path must be a string or PathLike"):
        _ = compiler_mod._parse_output_extra_sheet_override(OutputExtraSheetOverride(path=1), path="p")  # noqa: SLF001

    with pytest.raises(TypeError, match=r"p\.allow_formulas must be a bool"):
        _ = compiler_mod._parse_output_extra_sheet_override(
            OutputExtraSheetOverride(allow_formulas="nope"),
            path="p",
        )  # noqa: SLF001

    with pytest.raises(TypeError, match=r"p\.write_lock must be a bool"):
        _ = compiler_mod._parse_output_extra_sheet_override(
            OutputExtraSheetOverride(write_lock="nope"),
            path="p",
        )  # noqa: SLF001


def test_runtime_compiler_apply_output_extras_overrides_rejects_invalid_extras_type() -> None:
    overrides = RunOverrides()
    object.__setattr__(overrides, "output_extras", object())
    options = RunOptions(allowed_modules=frozenset(), overrides=overrides)

    with pytest.raises(TypeError, match=r"overrides\.output_extras must be an OutputExtrasOverride"):
        _ = compiler_mod._apply_output_extras_overrides(DemandConfig(), options=options)  # noqa: SLF001
