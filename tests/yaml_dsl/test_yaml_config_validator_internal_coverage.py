from scalim.dsl.by_yaml._internal.config_parsing.validator import ConfigValidator
from scalim.dsl.by_yaml._internal.config_parsing.loader import YamlDemandLoader
from scalim.dsl.by_yaml.runtime import effective_outputs as effective_outputs_mod
from scalim.dsl.by_yaml.schema_dsl.models import DemandConfig, OutputTargetConfig, OutputToConfig, OutputWriteConfig
from scalim.dsl.by_yaml.schema_dsl.output_enums import DEFAULT_BOOK_WRITE_MODE


def test_effective_book_write_mode_returns_default_when_book_missing() -> None:
    assert effective_outputs_mod.effective_book_write_mode(
        DemandConfig(),
        resources_override=None,
        book_id="report",
    ) == str(DEFAULT_BOOK_WRITE_MODE)


def test_effective_book_write_mode_reads_write_defaults_value() -> None:
    loader = YamlDemandLoader()
    config = loader.load_string(
        """
name: preflight_book_mode
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
      path: ./out.xlsx
      write_defaults:
        mode: sheet
""",
    )
    assert effective_outputs_mod.effective_book_write_mode(config, resources_override=None, book_id="report") == "sheet"


def test_output_item_requires_unique_effective_display_names_file_and_book_branches() -> None:
    loader = YamlDemandLoader()
    config = loader.load_string(
        """
name: preflight_output_unique_cov
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
      path: ./out.xlsx
      write_defaults:
        mode: sheet
""",
    )

    assert (
        effective_outputs_mod.output_target_requires_unique_effective_field_display_names(
            config,
            OutputTargetConfig(
                name="file",
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
            OutputTargetConfig(
                name="book",
                to=OutputToConfig(book="report", sheet="S"),
                write=OutputWriteConfig(header_fields_output_by="name", include_header=True),
                fields=("id",),
            ),
            resources_override=None,
        )
        is True
    )


def test_validator_validate_resource_output_paths_covers_init_var_errors_and_continue() -> None:
    v = ConfigValidator()
    errors = []
    v._validate_resource_output_paths(  # noqa: SLF001
        {
            "resources": {
                "files": {
                    "": {},  # continue branch
                    "detail_csv": {"path": {"$init_var": None}},
                },
                "books": {
                    "": {},  # continue branch
                    "report": {
                        "path": {"$init_var": None},
                        "export_xlsx": {"path": {"$init_var": None}},
                    },
                    "report2": {
                        "export_xlsx": {"path": "x.xlsx"},
                    },
                },
            }
        },
        errors,
    )
    assert errors
    assert any(i.path == "resources.files.detail_csv.path.$init_var" for i in errors)
    assert any(i.path == "resources.books.report.path.$init_var" for i in errors)
    assert any(i.path == "resources.books.report.export_xlsx.path.$init_var" for i in errors)


def test_output_target_requires_unique_effective_display_names_rejects_missing_destination_and_field_id_headers() -> None:
    config = DemandConfig()

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
                name="file_field_id_header",
                to=OutputToConfig(file="detail_csv"),
                write=OutputWriteConfig(header_fields_output_by="field_id"),
                fields=("id",),
            ),
            resources_override=None,
        )
        is False
    )
