from pathlib import Path
from typing import FrozenSet

import pytest

from scalim.dsl.yaml_dsl._internal.config_parsing.loader import YamlDemandLoader
from scalim.dsl.yaml_dsl import (
    BookResourceOverride,
    BookWriteDefaultsOverride,
    DemandDiagnosticsPolicy,
    OutputDefaultsToOverride,
    OutputOverride,
    OutputToOverride,
    OutputWriteOverride,
    OutputsDefaultsOverride,
    ResourcesOverride,
    RunOverrides,
)
from scalim.dsl.yaml_dsl.runtime.contracts import RunOptions
from scalim.dsl.yaml_dsl.runtime import effective_outputs as effective_outputs_mod
from scalim.dsl.yaml_dsl.schema_dsl.models import DemandConfig, OutputTargetConfig, OutputToConfig, OutputWriteConfig
from scalim.dsl.yaml_dsl import workflow_preflight as preflight_mod


def test_workflow_preflight_run_workflow_preflight_orders_and_dispatches() -> None:
    class RecordingCheck:
        check_id: str = "recording"

        def __init__(self) -> None:
            self.seen = []

        def run(self, ctx: preflight_mod.WorkflowPreflightContext, run: preflight_mod.WorkflowPreflightRun) -> None:
            self.seen.append((ctx.workflow_yaml_path, run.run_id, int(run.decl_order)))

    ctx = preflight_mod.WorkflowPreflightContext(workflow_yaml_path="./workflow.yaml")
    check0 = RecordingCheck()
    check1 = RecordingCheck()

    runs = (
        preflight_mod.WorkflowPreflightRun(
            run_id="r2",
            demand_path="./d2.yaml",
            decl_order=2,
            demand_config=DemandConfig(),
            options=RunOptions(allowed_modules=cast_frozenset()),
        ),
        preflight_mod.WorkflowPreflightRun(
            run_id="r0",
            demand_path="./d0.yaml",
            decl_order=0,
            demand_config=DemandConfig(),
            options=RunOptions(allowed_modules=cast_frozenset()),
        ),
        preflight_mod.WorkflowPreflightRun(
            run_id="r1",
            demand_path="./d1.yaml",
            decl_order=1,
            demand_config=DemandConfig(),
            options=RunOptions(allowed_modules=cast_frozenset()),
        ),
    )

    preflight_mod.run_workflow_preflight(ctx, runs=runs, checks=(check0, check1))

    assert check0.seen == [
        ("./workflow.yaml", "r0", 0),
        ("./workflow.yaml", "r1", 1),
        ("./workflow.yaml", "r2", 2),
    ]
    assert check1.seen == check0.seen


def test_workflow_preflight_run_workflow_preflight_fail_fast_stops_on_first_error() -> None:
    class FailFirstCheck:
        check_id: str = "fail_first"

        def __init__(self) -> None:
            self.seen = []

        def run(self, ctx: preflight_mod.WorkflowPreflightContext, run: preflight_mod.WorkflowPreflightRun) -> None:
            _ = ctx
            self.seen.append(run.run_id)
            if run.run_id == "r0":
                raise ValueError("boom")

    ctx = preflight_mod.WorkflowPreflightContext(workflow_yaml_path="./workflow.yaml")
    check = FailFirstCheck()

    runs = (
        preflight_mod.WorkflowPreflightRun(
            run_id="r1",
            demand_path="./d1.yaml",
            decl_order=1,
            demand_config=DemandConfig(),
            options=RunOptions(allowed_modules=cast_frozenset()),
        ),
        preflight_mod.WorkflowPreflightRun(
            run_id="r0",
            demand_path="./d0.yaml",
            decl_order=0,
            demand_config=DemandConfig(),
            options=RunOptions(allowed_modules=cast_frozenset()),
        ),
    )

    with pytest.raises(ValueError, match="boom"):
        preflight_mod.run_workflow_preflight(ctx, runs=runs, checks=(check,))

    assert check.seen == ["r0"]


def test_workflow_preflight_apply_default_book_binding_to_outputs_branches() -> None:
    assert effective_outputs_mod.apply_default_book_binding_to_outputs((), default_book_id="report") == ()

    outputs = (OutputTargetConfig(name="x", to=OutputToConfig(file="detail_csv")),)
    assert effective_outputs_mod.apply_default_book_binding_to_outputs(outputs, default_book_id="") == outputs

    outputs = (
        OutputTargetConfig(name="no_to", to=None),
        OutputTargetConfig(name="has_file", to=OutputToConfig(file="detail_csv")),
        OutputTargetConfig(name="needs_default", to=OutputToConfig()),
    )
    updated = effective_outputs_mod.apply_default_book_binding_to_outputs(outputs, default_book_id="report")
    assert updated[0].to is not None and updated[0].to.book == "report"
    assert updated[1] == outputs[1]
    assert updated[2].to is not None and updated[2].to.book == "report"


def test_workflow_preflight_effective_book_write_defaults_come_from_config() -> None:
    loader = YamlDemandLoader()
    config = loader.load_string(
        """
name: preflight_book_defaults
main_source:
  source_id: main
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    id: {extract: id}
sources: {}
resources:
  books:
    report:
      kind: xlsx_file
      path: ./out
      write_defaults:
        mode: sheet
        header_policy: never
"""
    )

    assert effective_outputs_mod.effective_book_write_mode(config, resources_override=None, book_id="report") == "sheet"
    assert effective_outputs_mod.effective_book_header_policy(config, resources_override=None, book_id="report") == "never"


def test_workflow_preflight_effective_book_write_defaults_can_be_overridden() -> None:
    loader = YamlDemandLoader()
    config = loader.load_string(
        """
name: preflight_book_defaults_override
main_source:
  source_id: main
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    id: {extract: id}
sources: {}
resources:
  books:
    report:
      kind: xlsx_file
      path: ./out
      write_defaults:
        mode: sheet
        header_policy: once
"""
    )

    resources_override = ResourcesOverride(
        books={
            "report": BookResourceOverride(write_defaults=BookWriteDefaultsOverride(mode="append", header_policy="never")),
        }
    )

    assert effective_outputs_mod.effective_book_write_mode(config, resources_override=resources_override, book_id="report") == "append"
    assert effective_outputs_mod.effective_book_header_policy(config, resources_override=resources_override, book_id="report") == "never"


def test_workflow_preflight_output_target_requires_unique_branches() -> None:
    loader = YamlDemandLoader()
    config = loader.load_string(
        """
name: preflight_output_target
main_source:
  source_id: main
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    id: {extract: id}
sources: {}
resources:
  books:
    report:
      kind: xlsx_file
      path: ./out
      write_defaults:
        mode: sheet
        header_policy: once
"""
    )

    assert (
        effective_outputs_mod.output_target_requires_unique_effective_field_display_names(
            config,
            OutputTargetConfig(name="no_to", to=None, fields=("id",)),
            resources_override=None,
        )
        is False
    )

    assert (
        effective_outputs_mod.output_target_requires_unique_effective_field_display_names(
            config,
            OutputTargetConfig(
                name="file_no_header",
                to=OutputToConfig(file="detail_csv"),
                write=OutputWriteConfig(include_header=False),
                fields=("id",),
            ),
            resources_override=None,
        )
        is False
    )

    assert (
        effective_outputs_mod.output_target_requires_unique_effective_field_display_names(
            config,
            OutputTargetConfig(name="sheet_only", to=OutputToConfig(sheet="S"), fields=("id",)),
            resources_override=None,
        )
        is False
    )

    assert (
        effective_outputs_mod.output_target_requires_unique_effective_field_display_names(
            config,
            OutputTargetConfig(
                name="book_no_header",
                to=OutputToConfig(book="report", sheet="S"),
                write=OutputWriteConfig(include_header=False),
                fields=("id",),
            ),
            resources_override=None,
        )
        is False
    )


def test_workflow_preflight_output_target_requires_unique_header_by_not_name_and_append() -> None:
    loader = YamlDemandLoader()
    config = loader.load_string(
        """
name: preflight_output_target_extra
main_source:
  source_id: main
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    id: {extract: id}
sources: {}
resources:
  books:
    report:
      kind: xlsx_file
      path: ./out
      write_defaults:
        mode: append
        header_policy: once
"""
    )

    assert (
        effective_outputs_mod.output_target_requires_unique_effective_field_display_names(
            config,
            OutputTargetConfig(
                name="file_header_by_field_id",
                to=OutputToConfig(file="detail_csv"),
                write=OutputWriteConfig(header_fields_output_by="field_id"),
                fields=("id",),
            ),
            resources_override=None,
        )
        is False
    )

    assert (
        effective_outputs_mod.output_target_requires_unique_effective_field_display_names(
            config,
            OutputTargetConfig(name="append_book", to=OutputToConfig(book="report", sheet="S"), fields=("id",)),
            resources_override=None,
        )
        is True
    )


def test_workflow_preflight_output_override_requires_unique_branches() -> None:
    loader = YamlDemandLoader()
    config = loader.load_string(
        """
name: preflight_output_override
main_source:
  source_id: main
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    id: {extract: id}
sources: {}
resources:
  books:
    report:
      kind: xlsx_file
      path: ./out
      write_defaults:
        mode: sheet
        header_policy: once
"""
    )

    assert (
        effective_outputs_mod.output_override_requires_unique_effective_field_display_names(
            config,
            OutputOverride(
                name="detail",
                fields=("id",),
                to=OutputToOverride(file="detail_csv"),
                write=OutputWriteOverride(include_header=False, header_fields_output_by="name"),
            ),
            default_book_id=None,
            resources_override=None,
        )
        is False
    )

    assert (
        effective_outputs_mod.output_override_requires_unique_effective_field_display_names(
            config,
            OutputOverride(
                name="detail",
                fields=("id",),
                to=OutputToOverride(sheet="S"),
                write=OutputWriteOverride(include_header=False, header_fields_output_by="name"),
            ),
            default_book_id="report",
            resources_override=None,
        )
        is False
    )

    assert (
        effective_outputs_mod.output_override_requires_unique_effective_field_display_names(
            config,
            OutputOverride(
                name="detail",
                fields=("id",),
                to=OutputToOverride(sheet="S"),
                write=OutputWriteOverride(header_fields_output_by="name"),
            ),
            default_book_id=None,
            resources_override=None,
        )
        is False
    )


def test_workflow_preflight_output_override_requires_unique_header_by_not_name_and_append() -> None:
    loader = YamlDemandLoader()
    config = loader.load_string(
        """
name: preflight_output_override_extra
main_source:
  source_id: main
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    id: {extract: id}
sources: {}
resources:
  books:
    report:
      kind: xlsx_file
      path: ./out
      write_defaults:
        mode: append
        header_policy: once
"""
    )

    assert (
        effective_outputs_mod.output_override_requires_unique_effective_field_display_names(
            config,
            OutputOverride(
                name="detail",
                fields=("id",),
                to=OutputToOverride(file="detail_csv"),
                write=OutputWriteOverride(header_fields_output_by="field_id"),
            ),
            default_book_id=None,
            resources_override=None,
        )
        is False
    )

    assert (
        effective_outputs_mod.output_override_requires_unique_effective_field_display_names(
            config,
            OutputOverride(
                name="detail",
                fields=("id",),
                to=OutputToOverride(book="report"),
                write=OutputWriteOverride(header_fields_output_by="name"),
            ),
            default_book_id=None,
            resources_override=None,
        )
        is True
    )


def test_workflow_preflight_effective_outputs_require_unique_branches() -> None:
    loader = YamlDemandLoader()
    config = loader.load_string(
        """
name: preflight_effective_outputs
main_source:
  source_id: main
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    id: {extract: id}
sources: {}
outputs:
  - name: detail
    fields: [id]
    to: {file: detail_csv}
"""
    )

    opts_with_outputs_override = RunOptions(
        allowed_modules=cast_frozenset(),
        overrides=RunOverrides(outputs=(OutputOverride(name="detail", fields=("id",), to=OutputToOverride(file="detail_csv")),)),
    )
    assert effective_outputs_mod.options_require_unique_effective_field_display_names(config, options=opts_with_outputs_override) is True

    opts_with_defaults = RunOptions(
        allowed_modules=cast_frozenset(),
        overrides=RunOverrides(outputs_defaults=OutputsDefaultsOverride(to=OutputDefaultsToOverride(book="report"))),
    )
    assert effective_outputs_mod.options_require_unique_effective_field_display_names(config, options=opts_with_defaults) is True


def test_workflow_preflight_effective_outputs_require_unique_returns_false_when_no_override_triggers() -> None:
    loader = YamlDemandLoader()
    config = loader.load_string(
        """
name: preflight_effective_outputs_override_false
main_source:
  source_id: main
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    id: {extract: id}
sources: {}
"""
    )

    options = RunOptions(
        allowed_modules=cast_frozenset(),
        overrides=RunOverrides(
            outputs=(
                OutputOverride(
                    name="detail",
                    fields=("id",),
                    to=OutputToOverride(file="detail_csv"),
                    write=OutputWriteOverride(header_fields_output_by="field_id"),
                ),
            )
        ),
    )
    assert effective_outputs_mod.options_require_unique_effective_field_display_names(config, options=options) is False


def test_workflow_preflight_effective_outputs_require_unique_returns_false_when_yaml_outputs_do_not_trigger() -> None:
    loader = YamlDemandLoader()
    config = loader.load_string(
        """
name: preflight_effective_outputs_yaml_false
main_source:
  source_id: main
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    id: {extract: id}
sources: {}
outputs:
  - name: detail
    fields: [id]
    to: {file: detail_csv}
    write: {header_fields_output_by: field_id}
"""
    )

    options = RunOptions(allowed_modules=cast_frozenset())
    assert effective_outputs_mod.options_require_unique_effective_field_display_names(config, options=options) is False


def test_workflow_preflight_collect_duplicate_effective_field_display_names_includes_derived_fields() -> None:
    loader = YamlDemandLoader()
    config = loader.load_string(
        """
name: preflight_duplicates
main_source:
  source_id: main
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    a: {extract: a, name: Dup}
    b: {extract: b, name: Dup}
sources: {}
fields:
  c:
    name: Dup
    compute: "1"
"""
    )

    duplicates = preflight_mod._collect_duplicate_effective_field_display_names(config)
    assert duplicates == {"Dup": ["a", "b", "c"]}


def _write_tmp_demand_yaml(tmp_path: Path, text: str, *, name: str = "demand.yaml") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_workflow_preflight_validate_unique_field_names_check_run_branches(tmp_path: Path) -> None:
    check = preflight_mod.ValidateUniqueFieldNamesPreflightCheck()
    ctx = preflight_mod.WorkflowPreflightContext(workflow_yaml_path=str(tmp_path / "workflow.yaml"))

    # 1) 显式禁用时应直接返回,且不应读取 demand YAML.
    run_disabled = preflight_mod.WorkflowPreflightRun(
        run_id="r0",
        demand_path=str(tmp_path / "missing.yaml"),
        decl_order=0,
        demand_config=DemandConfig(),
        options=RunOptions(allowed_modules=cast_frozenset(), demand_diagnostics=DemandDiagnosticsPolicy(validate_unique_field_names=False)),
    )
    check.run(ctx, run_disabled)

    loader = YamlDemandLoader()
    ok_config = loader.load_string(
        """
name: preflight_check_ok
main_source:
  source_id: main
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    a: {extract: a, name: A}
sources: {}
outputs:
  - name: detail
    fields: [a]
    to: {file: detail_csv}
    write: {header_fields_output_by: name}
""",
    )
    run_not_triggered = preflight_mod.WorkflowPreflightRun(
        run_id="r1",
        demand_path=str(tmp_path / "missing_ok.yaml"),
        decl_order=1,
        demand_config=ok_config,
        options=RunOptions(
            allowed_modules=cast_frozenset(),
            overrides=RunOverrides(
                outputs=(
                    OutputOverride(
                        name="detail",
                        fields=("a",),
                        to=OutputToOverride(file="detail_csv"),
                        write=OutputWriteOverride(header_fields_output_by="field_id"),
                    ),
                )
            ),
        ),
    )
    check.run(ctx, run_not_triggered)

    # 3) 触发但无重复,应返回.
    run_no_duplicates = preflight_mod.WorkflowPreflightRun(
        run_id="r2",
        demand_path=str(tmp_path / "missing_ok.yaml"),
        decl_order=2,
        demand_config=ok_config,
        options=RunOptions(allowed_modules=cast_frozenset()),
    )
    check.run(ctx, run_no_duplicates)

    # 4) 触发且存在重复,应抛出.
    dup_config = loader.load_string(
        """
name: preflight_check_dup
main_source:
  source_id: main
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    a: {extract: a, name: Dup}
    b: {extract: b, name: Dup}
sources: {}
outputs:
  - name: detail
    fields: [a, b]
    to: {file: detail_csv}
    write: {header_fields_output_by: name}
""",
    )
    run_has_duplicates = preflight_mod.WorkflowPreflightRun(
        run_id="r3",
        demand_path=str(tmp_path / "missing_dup.yaml"),
        decl_order=3,
        demand_config=dup_config,
        options=RunOptions(allowed_modules=cast_frozenset()),
    )
    with pytest.raises(preflight_mod.ScalimWorkflowConfigError, match=r"Workflow preflight failed: run_id='r3'"):
        check.run(ctx, run_has_duplicates)


def test_yaml_dsl_parser_only_loader_rejects_validate_unique_field_names_kwarg() -> None:
    loader = YamlDemandLoader()
    with pytest.raises(TypeError, match="validate_unique_field_names"):
        _ = loader.load_string("{}", validate_unique_field_names=False)  # type: ignore[call-arg] boundary regression test


def cast_frozenset() -> FrozenSet[str]:
    # `RunOptions.allowed_modules` is required but irrelevant for these pure preflight helpers.
    return frozenset()
