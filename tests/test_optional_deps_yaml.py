import importlib

import pytest

from tests.testing_utils import missing_optional_dependency


@pytest.mark.parametrize(
    "module_path,context",
    [
        ("scalim.dsl.by_yaml.config_parsing.loader", "scalim.dsl.by_yaml.config_parsing.loader"),
        ("scalim.dsl.by_yaml.config_parsing.validator", "scalim.dsl.by_yaml.config_parsing.validator"),
        ("scalim.cli.yaml_dsl", "scalim.cli.yaml_dsl"),
    ],
    ids=["loader", "validator", "cli"],
)
def test_yaml_import_errors_are_friendly(monkeypatch, module_path: str, context: str) -> None:
    module = importlib.import_module(module_path)

    with missing_optional_dependency(monkeypatch, "yaml"):
        with pytest.raises(ImportError) as excinfo:
            importlib.reload(module)

    msg = str(excinfo.value)
    assert context in msg
    assert "pip install pyyaml" in msg
    assert "pip install yaml" not in msg

    importlib.reload(module)
