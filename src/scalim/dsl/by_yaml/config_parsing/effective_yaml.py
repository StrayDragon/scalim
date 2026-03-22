from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Mapping, Optional, Union

from ....vendor.compact.importlibx import require_optional_dependency
from ....vendor.compact.typing_extensionsx import override

if TYPE_CHECKING:
    import yaml
else:
    yaml = require_optional_dependency(
        "yaml",
        context="scalim.dsl.by_yaml.config_parsing.effective_yaml",
        install_name="pyyaml",
    )

from .imports import contains_import_syntax, load_and_expand_imports

__all__ = [
    "dump_effective_demand_yaml",
    "load_effective_demand_yaml",
]


def load_effective_demand_yaml(
    yaml_path: Union[str, Path],
    *,
    template_vars: Optional[Mapping[str, object]] = None,
) -> Dict[str, Any]:
    """把需求 `YAML` 渲染为 `effective YAML`(展开 `template_vars` + `imports/$import`).

    约束:
    - `template_vars` 仅当显式提供(非 `None`)时才会启用 `LiteJinja2` 预编译.
    - 该函数只做“展开”,不做 `schema`/`semantic` 校验;用于 `review`/`debug`/对拍.
    - 输出映射不再包含 `imports`/`$import`(已展开).
    """
    path = Path(yaml_path).resolve()
    return load_and_expand_imports(path, template_vars=template_vars)


class _NoAliasSafeDumper(yaml.SafeDumper):  # type: ignore[name-defined]
    @override
    def ignore_aliases(self, data: object) -> bool:
        return True


def dump_effective_demand_yaml(mapping: Mapping[str, Any]) -> str:
    """把 `effective YAML` 映射序列化为 `YAML` 文本.

    要求输入已是 `effective YAML`(即不包含 `imports`/`$import`).
    """
    data = dict(mapping)
    if contains_import_syntax(data):
        msg = "dump_effective_demand_yaml expects effective YAML (no imports/$import); call load_effective_demand_yaml first"
        raise ValueError(msg)

    dumped: str = yaml.dump(  # type: ignore[no-any-return]
        data,
        allow_unicode=True,
        sort_keys=False,
        Dumper=_NoAliasSafeDumper,
    )
    return dumped
