import importlib

import pytest

from tests.support.testing_utils import missing_optional_dependency


@pytest.mark.parametrize(
    "module_path",
    [
        "scalim.dsl.by_yaml.config_parsing.loader",
        "scalim.dsl.by_yaml.config_parsing.validator",
        "scalim.cli.yaml_dsl",
    ],
    ids=["loader", "validator", "cli"],
)
def test_yaml_modules_do_not_require_external_pyyaml(monkeypatch, module_path: str) -> None:
    module = importlib.import_module(module_path)

    with missing_optional_dependency(monkeypatch, "yaml"):
        importlib.reload(module)

    if hasattr(module, "yaml"):
        yaml_mod = getattr(module, "yaml")
        assert isinstance(getattr(yaml_mod, "__file__", None), str)
        assert "/scalim/vendor/yamlx/yaml/" in str(yaml_mod.__file__).replace("\\", "/")
