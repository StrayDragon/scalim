from scalim.dsl.yaml_dsl._internal.config_parsing.validator import ConfigValidator
from scalim.dsl.yaml_dsl._internal.config_parsing.loader import YamlDemandLoader
from scalim.dsl.yaml_dsl.runtime import effective_outputs as effective_outputs_mod
from scalim.dsl.yaml_dsl.schema_dsl.models import (
    BookConfig,
    BookWriteDefaultsConfig,
    DemandConfig,
    OutputTargetConfig,
    OutputToConfig,
    OutputWriteConfig,
    ResourcesConfig,
)
from scalim.dsl.yaml_dsl.schema_dsl.output_enums import DEFAULT_BOOK_WRITE_MODE


def test_effective_book_write_mode_returns_default_when_book_missing() -> None:
    assert effective_outputs_mod.effective_book_write_mode(
        DemandConfig(),
        resources_override=None,
        book_id="report",
    ) == str(DEFAULT_BOOK_WRITE_MODE)


def test_effective_book_write_mode_reads_write_defaults_value() -> None:
    config = DemandConfig(
        resources=ResourcesConfig(
            books={
                "report": BookConfig(
                    path="./out",
                    write_defaults=BookWriteDefaultsConfig(mode="sheet"),
                ),
            }
        )
    )
    assert effective_outputs_mod.effective_book_write_mode(config, resources_override=None, book_id="report") == "sheet"


def test_output_item_requires_unique_effective_display_names_file_and_book_branches() -> None:
    config = DemandConfig(
        resources=ResourcesConfig(
            books={
                "report": BookConfig(
                    path="./out",
                    write_defaults=BookWriteDefaultsConfig(mode="sheet"),
                ),
            }
        )
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
                    "detail_csv": {"csv_file": {"path": {"$init_var": None}}},
                },
                "books": {
                    "": {},  # continue branch
                    "report": {
                        "xlsx_file": {"path": {"$init_var": None}},
                    },
                    "report2": {
                        "xlsx_memory": {"export_xlsx": {"path": "x.xlsx"}},
                    },
                    "ok": {
                        "xlsx": {"path": {"$init_var": None}},
                    },
                },
            }
        },
        errors,
    )
    assert errors
    assert any(i.path == "resources.files.detail_csv.csv_file.path.$init_var" for i in errors)
    assert any(i.path == "resources.books.report.xlsx_file" for i in errors)
    assert any(i.path == "resources.books.report2.xlsx_memory" for i in errors)
    assert any(i.path == "resources.books.ok.xlsx.path.$init_var" for i in errors)


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


def test_validator_error_and_strip_removed_resources_write_budget_fields_reports_and_strips() -> None:
    v = ConfigValidator()
    issues = []

    next_config = v._error_and_strip_removed_resources_write_budget_fields(  # noqa: SLF001
        {
            "resources": {
                "books": {
                    "bad": None,  # continue branch (non-dict)
                    "report": {
                        "kind": "xlsx_file",
                        "path": "./out",
                        "write_defaults": {"mode": "sheet"},
                    },
                    "mem": {
                        "kind": "xlsx_memory",
                        "write_defaults": {"mode": "sheet"},
                        "xlsx_memory": {
                            "budget": {"max_sheets": 1, "max_total_cells": 10},
                            "export_xlsx": {"path": "./out"},
                        },
                    },
                    "mem_budget_only": {
                        "kind": "xlsx_memory",
                        "xlsx_memory": {
                            "budget": {"max_sheets": 2, "max_total_cells": 20},
                        },
                    },
                }
            }
        },
        issues,
    )

    assert any(i.path == "resources.books.report.write_defaults" for i in issues)
    assert any(i.path == "resources.books.mem.write_defaults" for i in issues)
    assert any(i.path == "resources.books.mem.xlsx_memory.budget" for i in issues)
    assert any(i.path == "resources.books.mem_budget_only.xlsx_memory.budget" for i in issues)
    assert "write_defaults" not in next_config["resources"]["books"]["report"]
    assert "write_defaults" not in next_config["resources"]["books"]["mem"]
    assert "budget" not in next_config["resources"]["books"]["mem"]["xlsx_memory"]
    assert "budget" not in next_config["resources"]["books"]["mem_budget_only"]["xlsx_memory"]
    assert next_config["resources"]["books"]["mem"]["xlsx_memory"]["export_xlsx"]["path"] == "./out"


def test_validator_error_and_strip_removed_resources_write_lock_fields_reports_and_strips() -> None:
    v = ConfigValidator()
    issues = []

    next_config = v._error_and_strip_removed_resources_write_lock_fields(  # noqa: SLF001
        {
            "resources": {
                "files": {
                    "": {},  # continue branch (empty id)
                    "bad": None,  # continue branch (non-dict)
                    "detail_csv": {
                        "path": {"$init_var": "out_root"},
                        "write_lock": True,
                    },
                },
                "books": {
                    "": {},  # continue branch (empty id)
                    "bad": None,  # continue branch (non-dict)
                    "report": {
                        "kind": "xlsx_file",
                        "path": {"$init_var": "out_root"},
                        "write_lock": True,
                        "export_xlsx": {
                            "path": {"$init_var": "out_root"},
                            "write_lock": True,
                        },
                    },
                    "report2": {
                        "kind": "xlsx_memory",
                        "export_xlsx": {"path": {"$init_var": "out_root"}},  # continue branch (no write_lock)
                    },
                },
            }
        },
        issues,
    )

    assert any(i.path == "resources.files.detail_csv.write_lock" for i in issues)
    assert any(i.path == "resources.books.report.write_lock" for i in issues)
    assert any(i.path == "resources.books.report.export_xlsx.write_lock" for i in issues)

    assert "write_lock" not in next_config["resources"]["files"]["detail_csv"]
    assert "write_lock" not in next_config["resources"]["books"]["report"]
    assert "write_lock" not in next_config["resources"]["books"]["report"]["export_xlsx"]


def test_validator_validate_resource_output_paths_reports_removed_aliases() -> None:
    v = ConfigValidator()
    errors = []
    v._validate_resource_output_paths(  # noqa: SLF001
        {
            "resources": {
                "books": {
                    "report": {
                        "xlsx_file": {"path": "report.xlsx"},
                    },
                    "mem": {
                        "xlsx_memory": {"export_xlsx": {"path": "mem.xlsx"}},
                    },
                }
            }
        },
        errors,
    )
    assert errors
    assert any(i.path == "resources.books.report.xlsx_file" for i in errors)
    assert any("xlsx_file was removed" in i.message for i in errors)
    assert any(i.path == "resources.books.mem.xlsx_memory" for i in errors)
    assert any("xlsx_memory with export_xlsx was removed" in i.message for i in errors)
