from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union, cast

from .....vendor.compact.typing_extensionsx import TypeGuard
from .....vendor.dataclassesx import dataclass
from .....vendor.yamlx import yaml

__all__ = []


@dataclass(frozen=True)
class YamlDslProjectConfig:
    """`scalim.yaml` 解析结果(仅承载 `YAML DSL` 相关配置)."""

    scalim_yaml_path: Path
    project_root: Path
    import_aliases: Mapping[str, Path]
    import_allowed_roots: Tuple[Path, ...]


def _is_dict(value: object) -> TypeGuard[Dict[object, object]]:
    return isinstance(value, dict)


def _is_list(value: object) -> TypeGuard[List[object]]:
    return isinstance(value, list)


def _read_yaml_mapping(path: Path) -> Dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        msg = "scalim.yaml must be a mapping: path='{}'".format(str(path))
        raise TypeError(msg)
    return cast("Dict[str, Any]", loaded)  # pragma: allow-cast yaml.safe_load mapping typed narrowing


def _resolve_dir(value: object, *, base_dir: Path, context_label: str) -> Path:
    raw = str(value or "")
    if not raw.strip():
        msg = "{} must be a non-empty directory path".format(str(context_label or "path"))
        raise TypeError(msg)
    resolved = (base_dir / raw).expanduser().resolve(strict=False)
    if not resolved.exists() or not resolved.is_dir():
        msg = "{} must be an existing directory: raw='{}' | resolved='{}' | exists={} | is_dir={}".format(
            str(context_label or "path"),
            raw,
            str(resolved),
            bool(resolved.exists()),
            bool(resolved.is_dir()),
        )
        raise ValueError(msg)
    return resolved


def _parse_yaml_dsl_section(raw: Mapping[str, Any], *, scalim_yaml_path: Path) -> YamlDslProjectConfig:
    project_root = scalim_yaml_path.parent
    yaml_dsl = raw.get("yaml_dsl")
    yaml_dsl_dict: Dict[str, Any] = {}
    if yaml_dsl is None:
        yaml_dsl_dict = {}
    elif isinstance(yaml_dsl, dict):
        yaml_dsl_dict = cast("Dict[str, Any]", yaml_dsl)  # pragma: allow-cast yaml mapping typed narrowing
    else:
        msg = "scalim.yaml yaml_dsl must be a mapping: path='{}'".format(str(scalim_yaml_path))
        raise TypeError(msg)

    import_aliases: Dict[str, Path] = {}
    raw_aliases = yaml_dsl_dict.get("import_aliases")
    if raw_aliases is None:
        import_aliases = {}
    elif not _is_dict(raw_aliases):
        msg = "scalim.yaml yaml_dsl.import_aliases must be a mapping: path='{}'".format(str(scalim_yaml_path))
        raise TypeError(msg)
    else:
        for raw_key, raw_value in raw_aliases.items():
            if not isinstance(raw_key, str) or not raw_key.strip():
                msg = "scalim.yaml yaml_dsl.import_aliases keys must be non-empty strings: path='{}'".format(str(scalim_yaml_path))
                raise TypeError(msg)
            key = str(raw_key).strip()
            dir_path = _resolve_dir(raw_value, base_dir=project_root, context_label="yaml_dsl.import_aliases['{}']".format(key))
            import_aliases[key] = dir_path

    roots: Tuple[Path, ...] = ()
    raw_roots = yaml_dsl_dict.get("import_allowed_roots")
    if raw_roots is None:
        roots = ()
    elif not _is_list(raw_roots):
        msg = "scalim.yaml yaml_dsl.import_allowed_roots must be a list: path='{}'".format(str(scalim_yaml_path))
        raise TypeError(msg)
    else:
        resolved_roots: List[Path] = []
        for idx, raw_root in enumerate(raw_roots):
            resolved_roots.append(
                _resolve_dir(raw_root, base_dir=project_root, context_label="yaml_dsl.import_allowed_roots[{}]".format(idx))
            )
        roots = tuple(resolved_roots)

    return YamlDslProjectConfig(
        scalim_yaml_path=scalim_yaml_path,
        project_root=project_root,
        import_aliases=import_aliases,
        import_allowed_roots=roots,
    )


def _locate_scalim_yaml(
    *,
    start_dir: Path,
    scalim_yaml_override: Optional[Union[str, Path]] = None,
    project_root_override: Optional[Union[str, Path]] = None,
) -> Optional[Path]:
    if scalim_yaml_override is not None:
        path = Path(str(scalim_yaml_override)).expanduser().resolve(strict=False)
        if not path.exists() or not path.is_file():
            msg = "scalim.yaml override must exist and be a file: raw='{}' | resolved='{}' | exists={} | is_file={}".format(
                str(scalim_yaml_override),
                str(path),
                bool(path.exists()),
                bool(path.is_file()),
            )
            raise ValueError(msg)
        return path

    if project_root_override is not None:
        root = Path(str(project_root_override)).expanduser().resolve(strict=False)
        path = root / "scalim.yaml"
        if not path.exists() or not path.is_file():
            msg = "project_root override does not contain scalim.yaml: raw='{}' | resolved='{}'".format(
                str(project_root_override), str(path)
            )
            raise ValueError(msg)
        return path.resolve(strict=False)

    current = start_dir.resolve(strict=False)
    while True:
        candidate = current / "scalim.yaml"
        if candidate.exists() and candidate.is_file():
            return candidate.resolve(strict=False)
        parent = current.parent
        if parent == current:
            return None
        current = parent


def load_yaml_dsl_project_config(
    demand_yaml_path: Path,
    *,
    scalim_yaml_override: Optional[Union[str, Path]] = None,
    project_root_override: Optional[Union[str, Path]] = None,
) -> Optional[YamlDslProjectConfig]:
    """从 `demand YAML` 路径加载可选项目配置 `scalim.yaml`.

    规则:
    - 显式 `override` 优先(存在时必须不再向上查找).
    - 未提供 `override` 时使用 `nearest-wins`(从需求 `YAML` 文件所在目录向上查找最近的 `scalim.yaml`).
    """
    scalim_yaml_path = _locate_scalim_yaml(
        start_dir=demand_yaml_path.resolve(strict=False).parent,
        scalim_yaml_override=scalim_yaml_override,
        project_root_override=project_root_override,
    )
    if scalim_yaml_path is None:
        return None
    raw = _read_yaml_mapping(scalim_yaml_path)
    return _parse_yaml_dsl_section(raw, scalim_yaml_path=scalim_yaml_path)
