import pytest

from scalim.dsl.yaml_dsl.init_var_nodes import InitVarRef
from scalim.dsl.yaml_dsl._internal.config_parsing.loader import YamlDemandLoader
from scalim.dsl.yaml_dsl._internal.config_parsing.models import RawDemand
from scalim.dsl.yaml_dsl.book_resource_policy import BookBudgetPolicy, BookWriteMode, BookWritePolicy
from scalim.dsl.yaml_dsl.schema_dsl.models import (
    BOOK_BUDGET_KEYS,
    BOOK_EXPORT_XLSX_KEYS,
    BOOK_KEYS,
    DEMAND_KEYS,
    RESOURCES_KEYS,
    OutputTargetConfig,
    OutputToConfig,
    OutputWriteConfig,
)


def test_outputs_parser_book_binding_requires_explicit_to_book() -> None:
    loader = YamlDemandLoader()

    with pytest.raises(ValueError, match=r"outputs\.0\.to is required; declare exactly one of to\.file or to\.book"):
        loader._validate_output_binding_semantics(OutputTargetConfig(name="detail", fields=("a",)), idx=0)  # noqa: SLF001


def test_loader_parse_resources_book_mapping_errors_cover_branches() -> None:
    loader = YamlDemandLoader()

    raw = RawDemand.from_raw({DEMAND_KEYS["resources"]: {}})
    parsed = loader._parse_resources(raw)  # noqa: SLF001
    assert parsed is not None
    assert parsed.books == {}

    raw = RawDemand.from_raw({DEMAND_KEYS["resources"]: {RESOURCES_KEYS["books"]: "nope"}})
    with pytest.raises(TypeError, match=r"resources\.books must be an object"):
        _ = loader._parse_resources(raw)  # noqa: SLF001

    raw = RawDemand.from_raw({DEMAND_KEYS["resources"]: {RESOURCES_KEYS["books"]: {"": {BOOK_KEYS["xlsx_file"]: {"path": "./out"}}}}})
    with pytest.raises(ValueError, match=r"resources\.books key must be a non-empty string"):
        _ = loader._parse_resources(raw)  # noqa: SLF001

    raw = RawDemand.from_raw({DEMAND_KEYS["resources"]: {RESOURCES_KEYS["books"]: {"report": "nope"}}})
    with pytest.raises(TypeError, match=r"resources\.books\.report must be an object"):
        _ = loader._parse_resources(raw)  # noqa: SLF001


def test_loader_parse_book_config_semantic_errors_cover_branches() -> None:
    loader = YamlDemandLoader()

    with pytest.raises(ValueError, match=r"resources\.books\.report must choose exactly one variant key"):
        _ = loader._parse_book_config({}, base_path="resources.books.report")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"resources\.books\.report\.kind was removed"):
        _ = loader._parse_book_config({"kind": "xlsx_file", "path": "./out"}, base_path="resources.books.report")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"must choose exactly one variant key"):
        _ = loader._parse_book_config(
            {BOOK_KEYS["xlsx_file"]: {"path": "./out"}, BOOK_KEYS["xlsx_memory"]: {}},
            base_path="resources.books.report",
        )  # noqa: SLF001

    with pytest.raises(ValueError, match=r"resources\.books\.report\.xlsx_file\.path is required"):
        _ = loader._parse_book_config(
            {
                BOOK_KEYS["xlsx_file"]: {},
            },
            base_path="resources.books.report",
        )  # noqa: SLF001

    with pytest.raises(ValueError, match=r"xlsx_file has unknown keys"):
        _ = loader._parse_book_config(
            {
                BOOK_KEYS["xlsx_file"]: {
                    "path": "./out",
                    "budget": {BOOK_BUDGET_KEYS["max_sheets"]: 1, BOOK_BUDGET_KEYS["max_total_cells"]: 1},
                },
            },
            base_path="resources.books.report",
        )  # noqa: SLF001

    parsed = loader._parse_book_config({BOOK_KEYS["xlsx_memory"]: {}}, base_path="resources.books.report")  # noqa: SLF001
    assert parsed.kind == "xlsx_memory"
    assert parsed.budget is None

    with pytest.raises(ValueError, match=r"xlsx_memory has unknown keys"):
        _ = loader._parse_book_config(
            {
                BOOK_KEYS["xlsx_memory"]: {"path": "./out"},
            },
            base_path="resources.books.report",
        )  # noqa: SLF001

    with pytest.raises(ValueError, match=r"write_defaults was removed from YAML authoring"):
        _ = loader._parse_book_config(
            {
                BOOK_KEYS["xlsx_file"]: {"path": "./out"},
                "write_defaults": {},
            },
            base_path="resources.books.report",
        )  # noqa: SLF001

    with pytest.raises(ValueError, match=r"write_defaults was removed from YAML authoring"):
        _ = loader._parse_book_config(
            {BOOK_KEYS["xlsx_file"]: {"path": "./out"}, "write_defaults": []},
            base_path="resources.books.report",
        )  # noqa: SLF001


def test_loader_parse_book_config_additional_error_branches_cover_removed_write_lock_and_types() -> None:
    loader = YamlDemandLoader()

    with pytest.raises(ValueError, match=r"resources\.books\.report\.write_lock was removed"):
        _ = loader._parse_book_config(
            {"write_lock": True, BOOK_KEYS["xlsx_file"]: {"path": "./out"}},
            base_path="resources.books.report",
        )  # noqa: SLF001

    with pytest.raises(ValueError, match=r"resources\.books\.report\.kind was removed"):
        _ = loader._parse_book_config({"kind": "xlsx_memory"}, base_path="resources.books.report")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"resources\.books\.report\.kind was removed"):
        _ = loader._parse_book_config({"kind": "nope"}, base_path="resources.books.report")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"resources\.books\.report has unknown keys: unknown"):
        _ = loader._parse_book_config(
            {BOOK_KEYS["xlsx_file"]: {"path": "./out"}, "unknown": 1},
            base_path="resources.books.report",
        )  # noqa: SLF001
    with pytest.raises(TypeError, match=r"resources\.books\.report\.xlsx_file must be an object"):
        _ = loader._parse_book_config(
            {BOOK_KEYS["xlsx_file"]: []},
            base_path="resources.books.report",
        )  # noqa: SLF001

    with pytest.raises(TypeError, match=r"resources\.books\.report\.xlsx_memory must be an object"):
        _ = loader._parse_book_config(
            {BOOK_KEYS["xlsx_memory"]: []},
            base_path="resources.books.report",
        )  # noqa: SLF001

    with pytest.raises(ValueError, match=r"resources\.books\.report\.xlsx_file\.write_lock was removed"):
        _ = loader._parse_book_config(
            {BOOK_KEYS["xlsx_file"]: {"path": "./out", "write_lock": True}},
            base_path="resources.books.report",
        )  # noqa: SLF001

    with pytest.raises(ValueError, match=r"resources\.books\.report\.xlsx_memory\.write_lock was removed"):
        _ = loader._parse_book_config(
            {BOOK_KEYS["xlsx_memory"]: {"write_lock": True}},
            base_path="resources.books.report",
        )  # noqa: SLF001

    parsed = loader._parse_book_config(
        {BOOK_KEYS["xlsx_memory"]: {"export_xlsx": {"path": "./out"}}},
        base_path="resources.books.report",
    )  # noqa: SLF001
    assert parsed.export_xlsx is not None


def test_loader_parse_path_or_init_var_branches_cover_dict_and_error() -> None:
    loader = YamlDemandLoader()

    out = loader._parse_path_or_init_var({"$init_var": "p"}, path="p")  # noqa: SLF001
    assert isinstance(out, InitVarRef)
    assert out.name == "p"
    assert out.path == "p"

    with pytest.raises(TypeError, match=r"p must be a non-empty string or"):
        _ = loader._parse_path_or_init_var(1, path="p")  # noqa: SLF001


def test_loader_rejects_yaml_book_budget_authoring() -> None:
    loader = YamlDemandLoader()

    with pytest.raises(ValueError, match=r"xlsx_memory\.budget was removed from YAML authoring"):
        _ = loader._parse_book_config(  # noqa: SLF001
            {
                BOOK_KEYS["xlsx_memory"]: {
                    "budget": {BOOK_BUDGET_KEYS["max_sheets"]: 1, BOOK_BUDGET_KEYS["max_total_cells"]: 1},
                },
            },
            base_path="resources.books.report",
        )

    with pytest.raises(ValueError, match=r"xlsx_memory\.budget was removed from YAML authoring"):
        _ = loader._parse_book_config(  # noqa: SLF001
            {BOOK_KEYS["xlsx_memory"]: {"budget": {}}},
            base_path="resources.books.report",
        )

    with pytest.raises(ValueError, match=r"xlsx_memory\.budget was removed from YAML authoring"):
        _ = loader._parse_book_config(  # noqa: SLF001
            {BOOK_KEYS["xlsx_memory"]: {"budget": "nope"}},
            base_path="resources.books.report",
        )


def test_loader_parse_book_export_xlsx_branches_cover_success_and_error() -> None:
    loader = YamlDemandLoader()

    with pytest.raises(ValueError, match=r"e\.path is required"):
        _ = loader._parse_book_export_xlsx({}, base_path="e")  # noqa: SLF001

    cfg = loader._parse_book_export_xlsx({BOOK_EXPORT_XLSX_KEYS["path"]: "x.xlsx"}, base_path="e")  # noqa: SLF001
    assert cfg.path == "x.xlsx"


def test_loader_rejects_yaml_book_write_defaults_authoring() -> None:
    loader = YamlDemandLoader()

    with pytest.raises(ValueError, match=r"write_defaults was removed from YAML authoring"):
        _ = loader._parse_book_config(  # noqa: SLF001
            {
                BOOK_KEYS["xlsx_file"]: {"path": "./out"},
                "write_defaults": {"mode": "nope"},
            },
            base_path="resources.books.report",
        )

    with pytest.raises(ValueError, match=r"write_defaults was removed from YAML authoring"):
        _ = loader._parse_book_config(  # noqa: SLF001
            {
                BOOK_KEYS["xlsx_memory"]: {},
                "write_defaults": {"align_by": "nope"},
            },
            base_path="resources.books.report",
        )


def test_book_write_and_budget_policy_validation_cover_python_ssot() -> None:
    with pytest.raises(TypeError, match=r"BookWritePolicy\.mode must be a BookWriteMode"):
        _ = BookWritePolicy(mode="sheet")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match=r"BookWritePolicy\.align_by must be a BookWriteAlignBy"):
        _ = BookWritePolicy(mode=BookWriteMode.SHEET, align_by="field_id")  # type: ignore[arg-type]

    policy = BookWritePolicy()
    assert policy.to_write_defaults_config().mode == "sheet"

    with pytest.raises(TypeError, match=r"BookBudgetPolicy\.max_sheets must be an int or None"):
        _ = BookBudgetPolicy(max_sheets=True, max_total_cells=1)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match=r"BookBudgetPolicy\.max_total_cells must be an int or None"):
        _ = BookBudgetPolicy(max_sheets=1, max_total_cells=True)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match=r"BookBudgetPolicy\.max_sheets must be >= 1"):
        _ = BookBudgetPolicy(max_sheets=0, max_total_cells=1)

    with pytest.raises(ValueError, match=r"BookBudgetPolicy\.max_total_cells must be >= 1"):
        _ = BookBudgetPolicy(max_sheets=1, max_total_cells=0)

    with pytest.raises(ValueError, match=r"requires both max_sheets and max_total_cells"):
        _ = BookBudgetPolicy(max_sheets=1).as_options_mapping()


def test_outputs_parser_write_enum_errors_cover_branches() -> None:
    loader = YamlDemandLoader()

    with pytest.raises(ValueError, match=r"o\.mode was moved out of outputs\[\*\]\.write"):
        _ = loader._parse_output_write({"mode": "nope"}, base_path="o")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"o\.align_by was moved out of outputs\[\*\]\.write"):
        _ = loader._parse_output_write({"align_by": "nope"}, base_path="o")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"o\.header_policy was moved out of outputs\[\*\]\.write"):
        _ = loader._parse_output_write({"header_policy": "nope"}, base_path="o")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"o\.on_mismatch was moved out of outputs\[\*\]\.write"):
        _ = loader._parse_output_write({"on_mismatch": "nope"}, base_path="o")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"o\.on_conflict was moved out of outputs\[\*\]\.write"):
        _ = loader._parse_output_write({"on_conflict": "nope"}, base_path="o")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"o\.header_fields_output_by=.*expected one of"):
        _ = loader._parse_output_write({"header_fields_output_by": "nope"}, base_path="o")  # noqa: SLF001

    cfg = loader._parse_output_write({"header_fields_output_by": "field_id"}, base_path="o")  # noqa: SLF001
    assert cfg.header_fields_output_by == "field_id"


def test_outputs_parser_binding_semantics_errors_cover_branches() -> None:
    loader = YamlDemandLoader()

    with pytest.raises(ValueError, match=r"outputs\.0\.to is required"):
        t = OutputTargetConfig(name="detail", fields=("a",))
        loader._validate_output_binding_semantics(t, idx=0)  # noqa: SLF001

    with pytest.raises(ValueError, match=r"declare exactly one of to\.file or to\.book"):
        t = OutputTargetConfig(
            name="detail",
            to=OutputToConfig(file="detail_csv", book="report"),
            fields=("a",),
        )
        loader._validate_output_binding_semantics(t, idx=0)  # noqa: SLF001

    with pytest.raises(ValueError, match=r"to\.sheet requires outputs\.0\.to\.book"):
        t = OutputTargetConfig(
            name="detail",
            to=OutputToConfig(file="detail_csv", sheet="Detail"),
            fields=("a",),
        )
        loader._validate_output_binding_semantics(t, idx=0)  # noqa: SLF001
