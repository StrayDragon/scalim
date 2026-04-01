from typing import Any, Dict, cast

from ....vendor.yamlx import yaml


def safe_load_yaml_no_duplicates(text: str) -> object:
    """对 `yaml.safe_load` 增加重复 `key` 检测.

    需求: `workflow` 需要对资源 `id` 冲突等场景做提前校验; 这要求在解析阶段保留并检测重复 `key`.
    """

    class _Loader(yaml.SafeLoader):  # type: ignore[name-defined]
        pass

    def _construct_mapping(loader: object, node: object, deep: bool = False) -> Dict[object, object]:  # noqa: FBT001, FBT002
        mapping: Dict[object, object] = {}
        pairs = cast("Any", node).value  # pragma: allow-cast pyyaml loader typed narrowing
        for key_node, value_node in pairs:
            key = cast("Any", loader).construct_object(key_node, deep=deep)  # pragma: allow-cast pyyaml loader typed narrowing
            if key in mapping:
                msg = "Duplicate key in YAML mapping: {!r}".format(key)
                raise ValueError(msg)
            value = cast("Any", loader).construct_object(value_node, deep=deep)  # pragma: allow-cast pyyaml loader typed narrowing
            mapping[key] = value
        return mapping

    _Loader.add_constructor(  # type: ignore[attr-defined]
        cast("Any", yaml).resolver.BaseResolver.DEFAULT_MAPPING_TAG,  # pragma: allow-cast pyyaml resolver typed narrowing
        _construct_mapping,
    )
    return cast("Any", yaml).load(text, Loader=_Loader)  # pragma: allow-cast pyyaml loader typed narrowing


__all__ = ()
