import importlib

import pytest

from tests.testing_utils import missing_optional_dependency


@pytest.mark.parametrize(
    "module_path,missing_dep,error_match",
    [
        ("scalim.sinks.sink_excel", "openpyxl", "openpyxl"),
        ("scalim.sinks.sink_pandas", "pandas", "需要安装 pandas"),
    ],
    ids=["excel", "pandas"],
)
def test_optional_sink_import_errors(monkeypatch, module_path: str, missing_dep: str, error_match: str) -> None:
    module = importlib.import_module(module_path)

    with missing_optional_dependency(monkeypatch, missing_dep):
        with pytest.raises(ImportError, match=error_match):
            importlib.reload(module)
    importlib.reload(module)
