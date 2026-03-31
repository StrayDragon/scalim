from scalim.dsl.by_yaml._internal.config_parsing import validator as validator_mod
from scalim.dsl.by_yaml._internal.config_parsing.validator import ConfigValidator
from scalim.dsl.by_yaml.schema_dsl.models import BOOK_WRITE_DEFAULTS_KEYS


def test_raw_output_book_write_value_returns_default_when_structures_missing() -> None:
    assert (
        validator_mod._raw_output_book_write_value(  # noqa: SLF001
            {"resources": {"books": "nope"}},
            book_id="report",
            key=BOOK_WRITE_DEFAULTS_KEYS["mode"],
            default="sheet",
        )
        == "sheet"
    )

    assert (
        validator_mod._raw_output_book_write_value(  # noqa: SLF001
            {"resources": {"books": {"report": "nope"}}},
            book_id="report",
            key=BOOK_WRITE_DEFAULTS_KEYS["mode"],
            default="sheet",
        )
        == "sheet"
    )


def test_raw_output_book_write_value_reads_write_defaults_value_or_default() -> None:
    assert (
        validator_mod._raw_output_book_write_value(  # noqa: SLF001
            {"resources": {"books": {"report": {"write_defaults": {"mode": "append"}}}}},
            book_id="report",
            key=BOOK_WRITE_DEFAULTS_KEYS["mode"],
            default="sheet",
        )
        == "append"
    )


def test_output_item_requires_unique_effective_display_names_file_and_book_branches() -> None:
    assert (
        validator_mod._output_item_requires_unique_effective_display_names(  # noqa: SLF001
            {},
            {"to": {"file": "detail_csv"}, "write": {"include_header": False}},
        )
        is False
    )

    assert (
        validator_mod._output_item_requires_unique_effective_display_names(  # noqa: SLF001
            {},
            {"to": {"book": "report"}, "write": {"mode": "sheet", "include_header": True}},
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


def test_output_item_requires_unique_effective_display_names_rejects_non_mapping() -> None:
    assert validator_mod._output_item_requires_unique_effective_display_names({}, "nope") is False  # noqa: SLF001
