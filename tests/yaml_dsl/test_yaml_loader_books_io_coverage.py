import pytest

from scalim.dsl.by_yaml.config_parsing.loader import YamlDemandLoader
from scalim.dsl.by_yaml.config_parsing.models import RawDemand
from scalim.dsl.by_yaml.schema_dsl.models import (
    BOOK_BUDGET_KEYS,
    BOOK_EXPORT_XLSX_KEYS,
    BOOK_KEYS,
    BOOK_WRITE_DEFAULTS_KEYS,
    DEMAND_KEYS,
    RESOURCES_KEYS,
    OutputContainerConfig,
    OutputTargetConfig,
    OutputToConfig,
    OutputWriteConfig,
)


def test_outputs_parser_book_binding_requires_explicit_to_book() -> None:
    loader = YamlDemandLoader()

    with pytest.raises(ValueError, match=r"outputs\.0\.to\.book is required"):
        loader._validate_book_binding_semantics(OutputTargetConfig(name="detail", fields=("a",)), idx=0)  # noqa: SLF001


def test_loader_parse_resources_book_mapping_errors_cover_branches() -> None:
    loader = YamlDemandLoader()

    raw = RawDemand.from_raw({DEMAND_KEYS["resources"]: {}})
    parsed = loader._parse_resources(raw)  # noqa: SLF001
    assert parsed is not None
    assert parsed.books == {}

    raw = RawDemand.from_raw({DEMAND_KEYS["resources"]: {RESOURCES_KEYS["books"]: "nope"}})
    with pytest.raises(TypeError, match=r"resources\.books must be an object"):
        _ = loader._parse_resources(raw)  # noqa: SLF001

    raw = RawDemand.from_raw({DEMAND_KEYS["resources"]: {RESOURCES_KEYS["books"]: {"": {"kind": "xlsx_file", "path": "a.xlsx"}}}})
    with pytest.raises(ValueError, match=r"resources\.books key must be a non-empty string"):
        _ = loader._parse_resources(raw)  # noqa: SLF001

    raw = RawDemand.from_raw({DEMAND_KEYS["resources"]: {RESOURCES_KEYS["books"]: {"report": "nope"}}})
    with pytest.raises(TypeError, match=r"resources\.books\.report must be an object"):
        _ = loader._parse_resources(raw)  # noqa: SLF001


def test_loader_parse_book_config_semantic_errors_cover_branches() -> None:
    loader = YamlDemandLoader()

    with pytest.raises(ValueError, match=r"resources\.books\.report\.kind is required"):
        _ = loader._parse_book_config({}, base_path="resources.books.report")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"expected one of"):
        _ = loader._parse_book_config({BOOK_KEYS["kind"]: "nope"}, base_path="resources.books.report")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"path is required for kind=xlsx_file"):
        _ = loader._parse_book_config({BOOK_KEYS["kind"]: "xlsx_file"}, base_path="resources.books.report")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"budget is not allowed for kind=xlsx_file"):
        _ = loader._parse_book_config(
            {
                BOOK_KEYS["kind"]: "xlsx_file",
                BOOK_KEYS["path"]: "a.xlsx",
                BOOK_KEYS["budget"]: {BOOK_BUDGET_KEYS["max_sheets"]: 1, BOOK_BUDGET_KEYS["max_total_cells"]: 1},
            },
            base_path="resources.books.report",
        )  # noqa: SLF001

    with pytest.raises(ValueError, match=r"export_xlsx is not allowed for kind=xlsx_file"):
        _ = loader._parse_book_config(
            {
                BOOK_KEYS["kind"]: "xlsx_file",
                BOOK_KEYS["path"]: "a.xlsx",
                BOOK_KEYS["export_xlsx"]: {BOOK_EXPORT_XLSX_KEYS["path"]: "b.xlsx"},
            },
            base_path="resources.books.report",
        )  # noqa: SLF001

    with pytest.raises(ValueError, match=r"budget is required for kind=xlsx_memory"):
        _ = loader._parse_book_config({BOOK_KEYS["kind"]: "xlsx_memory"}, base_path="resources.books.report")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"path is not allowed for kind=xlsx_memory"):
        _ = loader._parse_book_config(
            {
                BOOK_KEYS["kind"]: "xlsx_memory",
                BOOK_KEYS["path"]: "a.xlsx",
                BOOK_KEYS["budget"]: {BOOK_BUDGET_KEYS["max_sheets"]: 1, BOOK_BUDGET_KEYS["max_total_cells"]: 1},
            },
            base_path="resources.books.report",
        )  # noqa: SLF001

    parsed = loader._parse_book_config(
        {
            BOOK_KEYS["kind"]: "xlsx_file",
            BOOK_KEYS["path"]: "a.xlsx",
            BOOK_KEYS["write_defaults"]: {},
        },
        base_path="resources.books.report",
    )  # noqa: SLF001
    assert parsed.write_defaults is not None


def test_loader_parse_path_or_init_var_branches_cover_dict_and_error() -> None:
    loader = YamlDemandLoader()

    out = loader._parse_path_or_init_var({"$init_var": "p"}, path="p")  # noqa: SLF001
    assert out == {"$init_var": "p"}

    with pytest.raises(TypeError, match=r"p must be a non-empty string or"):
        _ = loader._parse_path_or_init_var(1, path="p")  # noqa: SLF001


def test_loader_parse_book_budget_error_branches_cover_paths() -> None:
    loader = YamlDemandLoader()

    with pytest.raises(TypeError, match=r"b\.max_sheets must be an integer"):
        _ = loader._parse_book_budget({}, base_path="b")  # noqa: SLF001

    with pytest.raises(TypeError, match=r"b\.max_total_cells must be an integer"):
        _ = loader._parse_book_budget({BOOK_BUDGET_KEYS["max_sheets"]: 1}, base_path="b")  # noqa: SLF001

    with pytest.raises(TypeError, match=r"b\.max_sheets must be an integer"):
        _ = loader._parse_book_budget({BOOK_BUDGET_KEYS["max_sheets"]: "nope", BOOK_BUDGET_KEYS["max_total_cells"]: 1}, base_path="b")  # noqa: SLF001

    with pytest.raises(TypeError, match=r"b\.max_total_cells must be an integer"):
        _ = loader._parse_book_budget({BOOK_BUDGET_KEYS["max_sheets"]: 1, BOOK_BUDGET_KEYS["max_total_cells"]: "nope"}, base_path="b")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"b\.max_sheets must be >= 1"):
        _ = loader._parse_book_budget({BOOK_BUDGET_KEYS["max_sheets"]: 0, BOOK_BUDGET_KEYS["max_total_cells"]: 1}, base_path="b")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"b\.max_total_cells must be >= 1"):
        _ = loader._parse_book_budget({BOOK_BUDGET_KEYS["max_sheets"]: 1, BOOK_BUDGET_KEYS["max_total_cells"]: 0}, base_path="b")  # noqa: SLF001


def test_loader_parse_book_export_xlsx_branches_cover_success_and_error() -> None:
    loader = YamlDemandLoader()

    with pytest.raises(ValueError, match=r"e\.path is required"):
        _ = loader._parse_book_export_xlsx({}, base_path="e")  # noqa: SLF001

    cfg = loader._parse_book_export_xlsx({BOOK_EXPORT_XLSX_KEYS["path"]: "x.xlsx"}, base_path="e")  # noqa: SLF001
    assert cfg.path == "x.xlsx"


def test_loader_parse_book_write_defaults_branches_cover_invalid_enums_and_success() -> None:
    loader = YamlDemandLoader()

    with pytest.raises(ValueError, match=r"w\.mode=.*expected one of"):
        _ = loader._parse_book_write_defaults({BOOK_WRITE_DEFAULTS_KEYS["mode"]: "nope"}, base_path="w")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"w\.align_by=.*expected one of"):
        _ = loader._parse_book_write_defaults({BOOK_WRITE_DEFAULTS_KEYS["align_by"]: "nope"}, base_path="w")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"w\.header_policy=.*expected one of"):
        _ = loader._parse_book_write_defaults({BOOK_WRITE_DEFAULTS_KEYS["header_policy"]: "nope"}, base_path="w")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"w\.on_mismatch=.*expected one of"):
        _ = loader._parse_book_write_defaults({BOOK_WRITE_DEFAULTS_KEYS["on_mismatch"]: "nope"}, base_path="w")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"w\.on_conflict=.*expected one of"):
        _ = loader._parse_book_write_defaults({BOOK_WRITE_DEFAULTS_KEYS["on_conflict"]: "nope"}, base_path="w")  # noqa: SLF001

    cfg = loader._parse_book_write_defaults({}, base_path="w")  # noqa: SLF001
    assert str(cfg.mode)


def test_outputs_parser_write_enum_errors_cover_branches() -> None:
    loader = YamlDemandLoader()

    with pytest.raises(ValueError, match=r"o\.mode=.*expected one of"):
        _ = loader._parse_output_write({"mode": "nope"}, base_path="o")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"o\.align_by=.*expected one of"):
        _ = loader._parse_output_write({"align_by": "nope"}, base_path="o")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"o\.header_policy=.*expected one of"):
        _ = loader._parse_output_write({"header_policy": "nope"}, base_path="o")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"o\.on_mismatch=.*expected one of"):
        _ = loader._parse_output_write({"on_mismatch": "nope"}, base_path="o")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"o\.on_conflict=.*expected one of"):
        _ = loader._parse_output_write({"on_conflict": "nope"}, base_path="o")  # noqa: SLF001


def test_outputs_parser_container_semantics_errors_cover_branches() -> None:
    loader = YamlDemandLoader()

    base_container = OutputContainerConfig(type="csv", path="./out.csv", streaming=True)

    with pytest.raises(ValueError, match=r"cannot declare both container and to"):
        t = OutputTargetConfig(name="detail", container=base_container, to=OutputToConfig(book="report"), fields=("a",))
        loader._validate_output_container_semantics(t, "detail")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"cannot declare write for csv container outputs"):
        t = OutputTargetConfig(
            name="detail",
            container=base_container,
            write=OutputWriteConfig(mode="append"),
            fields=("a",),
        )
        loader._validate_output_container_semantics(t, "detail")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"expected 'csv'"):
        bad_container = OutputContainerConfig(type="json", path="./out.json", streaming=True)
        t = OutputTargetConfig(name="detail", container=bad_container, fields=("a",))
        loader._validate_output_container_semantics(t, "detail")  # noqa: SLF001
