import importlib

import pytest

from tests.support.testing_utils import missing_optional_dependency


@pytest.mark.parametrize(
    "module_path,missing_dep,error_match",
    [
        ("scalim.sinks._internal.excel", "openpyxl", "openpyxl"),
        ("scalim.sinks._internal.pandas", "pandas", "需要安装 pandas"),
    ],
    ids=["excel", "pandas"],
)
def test_optional_sink_import_errors(monkeypatch, module_path: str, missing_dep: str, error_match: str) -> None:
    module = importlib.import_module(module_path)

    with missing_optional_dependency(monkeypatch, missing_dep):
        with pytest.raises(ImportError, match=error_match):
            if module_path == "scalim.sinks._internal.excel":
                _ = module.ExcelSink("test.xlsx", field_names=["id"])  # type: ignore[attr-defined]
            elif module_path == "scalim.sinks._internal.pandas":
                sink = module.PandasRowSink()  # type: ignore[attr-defined]
                _ = sink.to_dataframe()
            else:
                raise AssertionError("Unexpected module_path: {}".format(module_path))
