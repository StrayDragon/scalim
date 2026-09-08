import importlib

import pytest

from tests.support.testing_utils import missing_optional_dependency


@pytest.mark.parametrize(
    "module_path",
    [
        "scalim.dsl.yaml_dsl._internal.config_parsing.loader",
        "scalim.dsl.yaml_dsl._internal.config_parsing.validator",
        "scalim_cli.yaml_dsl",
    ],
    ids=["loader", "validator", "cli"],
)
def test_yaml_modules_do_not_require_external_pyyaml(monkeypatch, module_path: str) -> None:
    module = importlib.import_module(module_path)

    # 0.20 起 PyYAML 不再是运行时依赖(vendored 拷贝已删除,oracle 仅为 dev 依赖):
    # 缺失 `yaml` 包时相关模块 MUST 仍可导入(运行时后端为 `ruamel.yaml`)。
    with missing_optional_dependency(monkeypatch, "yaml"):
        reloaded = importlib.reload(module)

    assert reloaded is module
