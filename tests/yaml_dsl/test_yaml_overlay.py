from pathlib import Path
from typing import Any

import pytest

from scalim.dsl.yaml_dsl.init_var_nodes import InitVarRef
from scalim.dsl.yaml_dsl import (
    BookResourceOverride,
    BookWriteDefaultsOverride,
    DemandRunOptions,
    DemandRunOutputOptions,
    DemandRunRuntimeOptions,
    DemandRunSecurityOptions,
    DemandRunTemplateOptions,
    DemandDiagnosticsPolicy,
    FileResourceOverride,
    OutputOverride,
    OutputExtrasOverride,
    OutputToOverride,
    OutputWriteOverride,
    ResourcesOverride,
    UNSET,
    RunOverrides,
    compile,
)
from scalim.dsl.yaml_dsl._internal.config_parsing.error_envelope import ScalimYamlValidationError
from scalim.ob.presets.viz import VizObserverConfig
from scalim.workflow.errors import ScalimWorkflowConfigError

_ALLOWED_MODULES = frozenset(["tests.fixtures.mock_loaders"])


def _options(*, allowed_modules=_ALLOWED_MODULES, init_vars=None, batch_size=UNSET, overrides=None, demand_diagnostics=None):  # type: ignore[no-untyped-def] test helper
    return DemandRunOptions(
        security=DemandRunSecurityOptions(allowed_modules=allowed_modules),
        template=DemandRunTemplateOptions(init_vars=init_vars),
        runtime=DemandRunRuntimeOptions(batch_size=batch_size, demand_diagnostics=demand_diagnostics),
        outputs=DemandRunOutputOptions(overrides=overrides),
    )


def _write_yaml(tmp_path: Path, text: str) -> Path:
    yaml_path = tmp_path / "overlay.yaml"
    yaml_path.write_text(text.strip() + "\n", encoding="utf-8")
    return yaml_path


def test_unset_repr() -> None:
    assert repr(UNSET) == "UNSET"


def test_compile_applies_output_overrides_and_export_layout(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
      name: Order ID
    amount:
      extract: amount
      name: Amount
sources: {}
    """,
    )

    out_root = tmp_path / "out"
    overrides = RunOverrides.xlsx_file_single_sheet(
        output_root=out_root,
        fields=("amount", "order_id"),
        sheet="Detail",
        output_name="detail",
        book_id="report",
        header_fields_output_by="name",
    )

    compilation = compile(
        str(yaml_path),
        options=_options(overrides=overrides),
    )
    request = compilation.request
    assert request.output_composition is not None
    assert len(request.output_composition.targets) == 1

    target = request.output_composition.targets[0]
    assert target.output.format == "excel"
    assert target.output.path is not None
    from scalim.execution.versioned_outputs import parse_versioned_output_path  # noqa: PLC0415

    parsed = parse_versioned_output_path(Path(str(target.output.path)))
    assert parsed.root == out_root.resolve(strict=False)
    assert parsed.kind == "books"
    assert parsed.artifact_id == "report"
    assert target.output.sheet_name == "Detail"
    assert target.output.include_header is True
    assert target.layout.field_ids == ("amount", "order_id")
    assert target.layout.header_names == ("Amount", "Order ID")


def test_compile_overrides_outputs_empty_rejected() -> None:
    with pytest.raises(ValueError, match=r"RunOverrides\.outputs cannot be empty"):
        _ = RunOverrides(outputs=[])


def test_run_overrides_outputs_legacy_dict_fail_fast() -> None:
    with pytest.raises(
        TypeError,
        match=r"Legacy YAML-shaped overrides are no longer supported: RunOverrides\.outputs=list\[dict\].*Migrate to typed dataclasses",
    ):
        _ = RunOverrides(outputs=[{"name": "detail"}])  # type: ignore[list-item]


@pytest.mark.parametrize(
    "make_overrides,exc_type,match",
    [
        (lambda: RunOverrides(outputs={"detail": 1}), TypeError, r"RunOverrides\.outputs must be a sequence of OutputOverride"),
        (lambda: RunOverrides(outputs=["detail"]), TypeError, r"RunOverrides\.outputs must be a sequence of OutputOverride"),
        (
            lambda: RunOverrides(outputs=(OutputOverride(name="", fields=("order_id",), to=OutputToOverride(file="detail_csv")),)),
            ScalimWorkflowConfigError,
            r"overrides\.outputs\.0\.name: .*Hint:",
        ),
        (
            lambda: RunOverrides(outputs=(OutputOverride(name="bad-name", fields=("order_id",), to=OutputToOverride(file="detail_csv")),)),
            ScalimWorkflowConfigError,
            r"overrides\.outputs\.0\.name: Invalid identifier.*Hint:",
        ),
        (
            lambda: RunOverrides(
                outputs=(
                    OutputOverride(name="detail", fields=("order_id",), to=OutputToOverride(file="detail_csv")),
                    OutputOverride(name="detail", fields=("order_id",), to=OutputToOverride(file="detail_csv")),
                )
            ),
            ScalimWorkflowConfigError,
            r"overrides\.outputs has duplicate output name: detail",
        ),
        (
            lambda: RunOverrides(outputs=(OutputOverride(name="detail", fields=(), to=OutputToOverride(file="detail_csv")),)),
            ScalimWorkflowConfigError,
            r"overrides\.outputs\.0\.fields must not be empty",
        ),
        (
            lambda: RunOverrides(outputs=(OutputOverride(name="detail", fields=("unknown",), to=OutputToOverride(file="detail_csv")),)),
            ScalimWorkflowConfigError,
            r"overrides\.outputs\.0\.fields reference unknown fields: unknown",
        ),
        (
            lambda: RunOverrides(
                outputs=(OutputOverride(name="detail", fields=("order_id",), to=OutputToOverride(file="detail_csv", sheet="Detail")),)
            ),
            ScalimWorkflowConfigError,
            r"overrides\.outputs\.0\.to\.sheet is not allowed with to\.file",
        ),
        (
            lambda: RunOverrides(
                outputs=(OutputOverride(name="detail", fields=("order_id",), to=OutputToOverride(file="detail_csv", book="report")),)
            ),
            ScalimWorkflowConfigError,
            r"overrides\.outputs\.0\.to must declare exactly one of to\.file or to\.book",
        ),
        (
            lambda: RunOverrides(outputs=(OutputOverride(name="detail", fields=("order_id",), to=OutputToOverride(sheet="Detail")),)),
            ScalimWorkflowConfigError,
            r"Missing output destination for overrides\.outputs\.0\.to",
        ),
        (
            lambda: RunOverrides(
                outputs=(
                    OutputOverride(
                        name="detail",
                        fields=("order_id",),
                        to=OutputToOverride(file="detail_csv"),
                        write=OutputWriteOverride(header_fields_output_by="bad"),
                    ),
                )
            ),
            ScalimWorkflowConfigError,
            r"overrides\.outputs\.0\.write\.header_fields_output_by='bad' is invalid",
        ),
        (
            lambda: RunOverrides(
                outputs=(
                    OutputOverride(
                        name="detail",
                        fields=("order_id",),
                        to=OutputToOverride(book="report", sheet="Detail"),
                        write=OutputWriteOverride(include_header=True),
                    ),
                ),
                resources=ResourcesOverride(
                    books={
                        "report": BookResourceOverride(
                            kind="xlsx_file",
                            path="./out",
                            write_defaults=BookWriteDefaultsOverride(mode="append"),
                        )
                    }
                ),
            ),
            ValueError,
            r"write\.include_header is not allowed for append-mode book outputs",
        ),
    ],
    ids=[
        "outputs-not-seq",
        "outputs-item-not-output-override",
        "name-required",
        "name-invalid-pattern",
        "duplicate-name",
        "fields-empty",
        "fields-unknown",
        "to-sheet-not-allowed-with-file",
        "to-file-and-book-conflict",
        "missing-destination",
        "write-header-by-invalid",
        "append-book-output-include-header-not-allowed",
    ],
)
def test_compile_overrides_outputs_rejects_invalid_payloads(tmp_path: Path, make_overrides, exc_type, match: str) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_overrides_outputs_invalid
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id: {extract: order_id}
sources: {}
""",
    )

    with pytest.raises(exc_type, match=match):
        overrides = make_overrides()
        _ = compile(
            str(yaml_path),
            options=_options(overrides=overrides),
        )


def test_compile_overrides_outputs_supports_init_var_path(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_overrides_outputs_init_var
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id: {extract: order_id}
sources: {}
""",
    )

    output_root = str(tmp_path / "out")
    compilation = compile(
        str(yaml_path),
        options=_options(
            init_vars={"out_path": output_root},
            overrides=RunOverrides(
                outputs=(OutputOverride(name="detail", fields=("order_id",), to=OutputToOverride(file="detail_csv")),),
                resources=ResourcesOverride(
                    files={
                        "detail_csv": FileResourceOverride(
                            kind="csv_file",
                            path=InitVarRef(name="out_path", path="overrides.resources.files.detail_csv.path"),
                        )
                    }
                ),
            ),
        ),
    )

    assert compilation.request.output_composition is not None
    out_path = Path(str(compilation.request.output_composition.targets[0].output.path))
    from scalim.execution.versioned_outputs import parse_versioned_output_path  # noqa: PLC0415

    parsed = parse_versioned_output_path(out_path)
    assert parsed.root == Path(str(output_root)).resolve(strict=False)
    assert parsed.kind == "files"
    assert parsed.artifact_id == "detail_csv"


def test_compile_overrides_outputs_supports_pathlike_path(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_overrides_outputs_pathlike
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id: {extract: order_id}
sources: {}
""",
    )

    output_root = tmp_path / "out"
    compilation = compile(
        str(yaml_path),
        options=_options(
            overrides=RunOverrides(
                outputs=(OutputOverride(name="detail", fields=("order_id",), to=OutputToOverride(file="detail_csv")),),
                resources=ResourcesOverride(files={"detail_csv": FileResourceOverride(kind="csv_file", path=output_root)}),
            )
        ),
    )

    assert compilation.request.output_composition is not None
    out_path = Path(str(compilation.request.output_composition.targets[0].output.path))
    from scalim.execution.versioned_outputs import parse_versioned_output_path  # noqa: PLC0415

    parsed = parse_versioned_output_path(out_path)
    assert parsed.root == output_root.resolve(strict=False)
    assert parsed.kind == "files"
    assert parsed.artifact_id == "detail_csv"


def test_compile_yaml_resources_file_path_supports_init_var_node(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_resource_path_init_var
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id: {extract: order_id}
sources: {}
resources:
  files:
    detail_csv:
      csv_file:
        path: {$init_var: out_path}
outputs:
  - name: detail
    to: {file: detail_csv}
    fields: [order_id]
""",
    )

    output_root = tmp_path / "out"
    compilation = compile(
        str(yaml_path),
        options=_options(init_vars={"out_path": str(output_root)}),
    )

    assert compilation.request.output_composition is not None
    out_path = Path(str(compilation.request.output_composition.targets[0].output.path))
    from scalim.execution.versioned_outputs import parse_versioned_output_path  # noqa: PLC0415

    parsed = parse_versioned_output_path(out_path)
    assert parsed.root == output_root.resolve(strict=False)
    assert parsed.kind == "files"
    assert parsed.artifact_id == "detail_csv"


def test_compile_overrides_outputs_disables_implicit_meta_without_workbook(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_overrides_outputs_meta
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id: {extract: order_id}
sources: {}
""",
    )

    compilation = compile(
        str(yaml_path),
        options=_options(
            overrides=RunOverrides(
                output_extras=OutputExtrasOverride(meta=True),
                outputs=(OutputOverride(name="detail", fields=("order_id",), to=OutputToOverride(file="detail_csv")),),
                resources=ResourcesOverride(files={"detail_csv": FileResourceOverride(kind="csv_file", path="./out")}),
            )
        ),
    )

    assert compilation.request.output_composition is not None
    assert compilation.request.output_composition.meta_sheet is None


def test_validate_unique_field_names_runtime_rejects_duplicates_triggered_by_overrides(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_unique_names_runtime
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id: {extract: order_id, name: ID}
    amount: {extract: amount, name: ID}
sources: {}
""",
    )

    with pytest.raises(ValueError, match=r"Duplicate effective field display names detected"):
        _ = compile(
            str(yaml_path),
            options=_options(
                overrides=RunOverrides(
                    outputs=(
                        OutputOverride(
                            name="detail",
                            fields=("order_id", "amount"),
                            to=OutputToOverride(file="detail_csv"),
                            write=OutputWriteOverride(header_fields_output_by="name"),
                        ),
                    ),
                    resources=ResourcesOverride(files={"detail_csv": FileResourceOverride(kind="csv_file", path="./out")}),
                )
            ),
        )


def test_should_validate_unique_field_names_skips_field_id_headers() -> None:
    from scalim.dsl.yaml_dsl._internal.config_parsing.loader import YamlDemandLoader
    from scalim.dsl.yaml_dsl.runtime import compiler as compiler_mod
    from scalim.dsl.yaml_dsl.schema_dsl.models import OutputTargetConfig, OutputToConfig, OutputWriteConfig

    loader = YamlDemandLoader()
    config = loader.load_string(
        """
name: overlay_unique_names_skip_field_id
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id: {extract: order_id}
sources: {}
resources:
  files:
    detail_csv: {csv_file: {path: ./out}}
"""
    )

    outputs = (
        OutputTargetConfig(
            name="base",
            from_=None,
            to=OutputToConfig(file="detail_csv"),
            write=OutputWriteConfig(header_fields_output_by="field_id"),
            fields=("order_id",),
            where=None,
            aggregate=None,
            requires=(),
        ),
        OutputTargetConfig(
            name="derived",
            from_="base",
            fields=("order_id",),
            where=None,
            aggregate=None,
            requires=(),
        ),
    )

    assert compiler_mod._should_validate_unique_effective_field_display_names(config, outputs) is False  # noqa: SLF001


def test_should_validate_unique_field_names_includes_books_outputs() -> None:
    from scalim.dsl.yaml_dsl._internal.config_parsing.loader import YamlDemandLoader
    from scalim.dsl.yaml_dsl.runtime import compiler as compiler_mod
    from scalim.dsl.yaml_dsl.schema_dsl.models import OutputTargetConfig, OutputToConfig

    loader = YamlDemandLoader()
    config = loader.load_string(
        """
name: overlay_unique_names_books
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id: {extract: order_id}
sources: {}
resources:
  books:
    report: {xlsx_file: {path: ./out}}
"""
    )

    outputs = (
        OutputTargetConfig(
            name="detail",
            to=OutputToConfig(book="report", sheet="明细"),
            fields=("order_id",),
            where=None,
            aggregate=None,
            requires=(),
        ),
    )

    assert compiler_mod._should_validate_unique_effective_field_display_names(config, outputs) is True  # noqa: SLF001


def test_validate_unique_field_names_rejects_duplicates_by_default(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_unique_names_default
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
      name: ID
    amount:
      extract: amount
      name: ID
sources: {}
outputs:
  - name: detail
    to: {file: detail_csv}
    fields: [order_id, amount]
resources:
  files:
    detail_csv: {csv_file: {path: ./out}}
""",
    )

    with pytest.raises(ValueError, match=r"Duplicate effective field display names detected") as excinfo:
        _ = compile(str(yaml_path), options=_options())
    msg = str(excinfo.value)
    assert "'ID'" in msg
    assert "order_id" in msg
    assert "amount" in msg


def test_validate_unique_field_names_rejects_duplicates_for_books_by_default(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_unique_names_books_default
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
      name: ID
    amount:
      extract: amount
      name: ID
sources: {}
resources:
  books:
    report:
      xlsx_file:
        path: ./out
outputs:
  - name: detail
    to: {book: report, sheet: 明细}
    fields: [order_id, amount]
""",
    )

    with pytest.raises(ValueError, match=r"Duplicate effective field display names detected") as excinfo:
        _ = compile(str(yaml_path), options=_options())
    msg = str(excinfo.value)
    assert "'ID'" in msg
    assert "order_id" in msg
    assert "amount" in msg


def test_validate_unique_field_names_can_be_disabled(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_unique_names_disabled
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
      name: ID
    amount:
      extract: amount
      name: ID
sources: {}
outputs:
  - name: detail
    to: {file: detail_csv}
    fields: [order_id, amount]
resources:
  files:
    detail_csv: {csv_file: {path: ./out}}
""",
    )

    compilation = compile(
        str(yaml_path),
        options=_options(demand_diagnostics=DemandDiagnosticsPolicy(validate_unique_field_names=False)),
    )
    assert compilation.config.validate_unique_field_names is False
    assert compilation.request.output_composition is not None


def test_compile_viz_config_override_enables_viz_without_yaml_observability(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_viz_enable
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
""",
    )

    viz_config = VizObserverConfig(
        output_path=str(tmp_path / "events.jsonl"),
        snapshot_path=str(tmp_path / "snapshot.json"),
    )
    overrides = RunOverrides(viz_config=viz_config)

    compilation = compile(
        str(yaml_path),
        options=_options(overrides=overrides),
    )
    assert compilation.request.observability is not None
    assert compilation.request.observability.viz_config is viz_config


def test_compile_legacy_yaml_observability_is_ignored_and_emits_migration_warning(tmp_path: Path, caplog: Any) -> None:
    import logging

    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_viz_disable
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
observability:
  viz:
    enabled: true
    output_dir: ./tmp
""",
    )

    caplog.set_level(logging.WARNING)
    compilation = compile(str(yaml_path), options=_options())
    assert compilation.request.observability is None
    assert any("Legacy YAML key 'observability' is no longer supported" in str(r.message) for r in caplog.records)


def test_compile_viz_config_override_overrides_yaml_observability(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_viz_override
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
observability:
  logging:
    enabled: true
    renderer: logger
""",
    )

    viz_config = VizObserverConfig(
        output_path=str(tmp_path / "events.jsonl"),
        snapshot_path=str(tmp_path / "snapshot.json"),
    )
    overrides = RunOverrides(viz_config=viz_config)

    compilation = compile(
        str(yaml_path),
        options=_options(overrides=overrides),
    )
    assert compilation.request.observability is not None
    assert compilation.request.observability.viz_config is viz_config


def test_compile_rejects_yaml_batch_size(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_batch_size_null
batch_size: null
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
""",
    )

    with pytest.raises(ScalimYamlValidationError) as excinfo:
        _ = compile(str(yaml_path), options=_options())

    assert any(env.path == "batch_size" for env in excinfo.value.errors)


def test_compile_batch_size_option_applies(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_batch_size_override
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
""",
    )

    compilation = compile(
        str(yaml_path),
        options=_options(batch_size=256),
    )
    config = compilation.config
    request = compilation.request

    assert config.batch_size == 256
    assert request.batch_size == 256


def test_compile_batch_size_option_rejects_invalid_type(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_batch_size_invalid_type
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
""",
    )

    with pytest.raises(TypeError, match=r"batch_size must be an integer >= 1"):
        _ = compile(
            str(yaml_path),
            options=_options(batch_size=True),  # type: ignore[arg-type] intentional runtime boundary test
        )


def test_compile_batch_size_option_rejects_non_positive_int(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_batch_size_invalid_value
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
""",
    )

    with pytest.raises(ValueError, match=r"batch_size must be >= 1"):
        _ = compile(
            str(yaml_path),
            options=_options(batch_size=0),
        )


def test_loader_parse_config_rejects_invalid_validate_unique_field_names_type() -> None:
    from scalim.dsl.yaml_dsl._internal.config_parsing.loader import YamlDemandLoader
    from scalim.dsl.yaml_dsl._internal.config_parsing.models import RawDemand

    loader = YamlDemandLoader()
    raw = RawDemand.from_raw(
        {
            "name": "overlay_unique_names_type_error",
            "validate_unique_field_names": 1,
            "main_source": {
                "source_id": "orders",
                "loader": "tests.fixtures.mock_loaders.mock_loader",
                "fields": {"order_id": {"extract": "order_id"}},
            },
            "sources": {},
            "relations": {},
            "fields": {},
            "outputs": [],
        }
    )
    with pytest.raises(ValueError, match=r"validate_unique_field_names.*moved out of demand YAML mainline"):
        loader._parse_config(raw)  # type: ignore[attr-defined]
