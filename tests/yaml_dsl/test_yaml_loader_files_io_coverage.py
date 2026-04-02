import pytest

from scalim.dsl.by_yaml._internal.config_parsing.loader import YamlDemandLoader
from scalim.dsl.by_yaml._internal.config_parsing.models import RawDemand
from scalim.dsl.by_yaml.schema_dsl.models import (
    DEMAND_KEYS,
    FILE_KEYS,
    RESOURCES_KEYS,
)


def test_loader_parse_resources_file_mapping_errors_cover_branches() -> None:
    loader = YamlDemandLoader()

    raw = RawDemand.from_raw({DEMAND_KEYS["resources"]: {}})
    parsed = loader._parse_resources(raw)  # noqa: SLF001
    assert parsed is not None
    assert parsed.files == {}

    raw = RawDemand.from_raw({DEMAND_KEYS["resources"]: {RESOURCES_KEYS["files"]: "nope"}})
    with pytest.raises(TypeError, match=r"resources\.files must be an object"):
        _ = loader._parse_resources(raw)  # noqa: SLF001

    raw = RawDemand.from_raw({DEMAND_KEYS["resources"]: {RESOURCES_KEYS["files"]: {"": {"kind": "csv_file", "path": "a.csv"}}}})
    with pytest.raises(ValueError, match=r"resources\.files key must be a non-empty string"):
        _ = loader._parse_resources(raw)  # noqa: SLF001

    raw = RawDemand.from_raw({DEMAND_KEYS["resources"]: {RESOURCES_KEYS["files"]: {"detail_csv": "nope"}}})
    with pytest.raises(TypeError, match=r"resources\.files\.detail_csv must be an object"):
        _ = loader._parse_resources(raw)  # noqa: SLF001


def test_loader_parse_file_config_semantic_errors_cover_branches() -> None:
    loader = YamlDemandLoader()

    with pytest.raises(ValueError, match=r"resources\.files\.detail_csv\.kind is required"):
        _ = loader._parse_file_config({}, base_path="resources.files.detail_csv")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"expected one of"):
        _ = loader._parse_file_config({FILE_KEYS["kind"]: "nope"}, base_path="resources.files.detail_csv")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"path is required for kind=csv_file"):
        _ = loader._parse_file_config({FILE_KEYS["kind"]: "csv_file"}, base_path="resources.files.detail_csv")  # noqa: SLF001


def test_outputs_parser_write_include_header_type_error_cover_branches() -> None:
    loader = YamlDemandLoader()

    with pytest.raises(TypeError, match=r"o\.include_header must be a boolean"):
        _ = loader._parse_output_write({"include_header": "yes"}, base_path="o")  # noqa: SLF001


def test_outputs_parser_write_rejects_removed_workbook_keys_cover_branches() -> None:
    loader = YamlDemandLoader()

    with pytest.raises(ValueError, match=r"o\.on_conflict was moved out of outputs\[\*\]\.write"):
        _ = loader._parse_output_write({"on_conflict": "error"}, base_path="o")  # noqa: SLF001
