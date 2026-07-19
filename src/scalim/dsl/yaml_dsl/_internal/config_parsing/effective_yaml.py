from io import StringIO
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Union

from .....vendor.yamlx.ruamel.yaml import YAML
from .imports import contains_import_syntax, load_and_expand_imports

__all__ = ()


def load_effective_demand_yaml(
    yaml_path: Union[str, Path],
    *,
    template_vars: Optional[Mapping[str, Any]] = None,
    template_sandbox: str = "safe",
    allowed_yaml_roots: Optional[Sequence[Union[str, Path]]] = None,
    scalim_yaml_override: Optional[Union[str, Path]] = None,
    project_root_override: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """把需求 `YAML` 渲染为 `effective YAML`(展开 `template_vars` + `imports/$import`).

    约束:
    - `template_vars` 仅当显式提供(非 `None`)时才会启用 `LiteJinja2` 预编译.
    - 该函数只做“展开”,不做 `schema`/`semantic` 校验;用于 `review`/`debug`/对拍.
    - 输出映射不再包含 `imports`/`$import`(已展开).
    """
    path = Path(yaml_path).resolve()
    return load_and_expand_imports(
        path,
        template_vars=template_vars,
        template_sandbox=template_sandbox,
        allowed_yaml_roots=allowed_yaml_roots,
        scalim_yaml_override=scalim_yaml_override,
        project_root_override=project_root_override,
    )


def dump_effective_demand_yaml(mapping: Mapping[str, Any]) -> str:
    """把 `effective YAML` 映射序列化为 `YAML` 文本.

    要求输入已是 `effective YAML`(即不包含 `imports`/`$import`).
    """
    data = dict(mapping)
    if contains_import_syntax(data):
        msg = "dump_effective_demand_yaml expects effective YAML (no imports/$import); call load_effective_demand_yaml first"
        raise ValueError(msg)

    yaml_safe = YAML(typ="safe")
    yaml_safe.default_flow_style = False
    yaml_safe.sort_base_mapping_type_on_output = False  # pyright: ignore[reportAttributeAccessIssue]  # pragma: allow-dynattr third-party: ruamel YAML config

    def _ignore_aliases(_data: Any) -> bool:
        return True

    yaml_safe.representer.ignore_aliases = _ignore_aliases  # type: ignore[assignment]  # pragma: allow-dynattr ruamel config

    buf = StringIO()
    yaml_safe.dump(data, buf)
    return buf.getvalue()
