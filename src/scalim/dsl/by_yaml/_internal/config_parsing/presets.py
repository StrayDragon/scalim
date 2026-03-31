from typing import Dict

__all__ = []


_YAML_PRESET_REGISTRY: Dict[str, str] = {
    # 说明: 注册表为 `SSOT`;仅允许预定义的 `preset_id`,避免变成“任意读包内路径”.
    "yaml-dsl/presets/common.yaml": (
        """
demo:
  x: 1
""".lstrip()
    ),
}


def load_scalim_preset_yaml_text(preset_id: str) -> str:
    """加载 `scalim://...` 预设的 `YAML` 文本(只读、本地、白名单)."""
    key = str(preset_id or "").strip()
    if not key:
        msg = "scalim:// preset id cannot be empty"
        raise ValueError(msg)
    if key not in _YAML_PRESET_REGISTRY:
        msg = "Unknown scalim:// preset id: '{}'".format(key)
        raise ValueError(msg)
    return str(_YAML_PRESET_REGISTRY[key])
