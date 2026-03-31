import pytest

from scalim.dsl.by_yaml._internal.config_parsing.loader import YamlDemandLoader
from scalim.dsl.by_yaml._internal.config_parsing.models import RawDemand


def test_loader_parse_config_rejects_invalid_failure_policy() -> None:
    loader = YamlDemandLoader()

    raw = RawDemand.from_raw(
        {
            "name": "demo",
            "main_source": {"source_id": "orders", "loader": "tests.fixtures.mock_loaders.mock_loader"},
            "failure_policy": "bad",
        }
    )

    with pytest.raises(ValueError, match=r"failure_policy must be 'all_fail' or 'primary_only'"):
        loader._parse_config(raw)


def test_loader_parse_extra_sheet_rejects_non_bool_non_object() -> None:
    loader = YamlDemandLoader()

    with pytest.raises(TypeError, match=r"meta must be a boolean or an object"):
        _ = loader._parse_extra_sheet("bad", key="meta")


def test_loader_parse_extra_sheet_parses_object_form() -> None:
    loader = YamlDemandLoader()

    sheet = loader._parse_extra_sheet(
        {
            "path": "./out.xlsx",
            "sheet": "__audit__",
            "allow_formulas": True,
            "write_lock": False,
        },
        key="audit",
    )
    assert sheet is not None
    assert sheet.path == "./out.xlsx"
    assert sheet.sheet == "__audit__"
    assert sheet.allow_formulas is True
    assert sheet.write_lock is False
