from pathlib import Path
from typing import Dict, Iterable, Optional, Sequence, Tuple, Union

__all__ = [
    "normalize_allowed_yaml_roots",
    "validate_resolved_yaml_path_within_roots",
]


def normalize_allowed_yaml_roots(
    allowed_yaml_roots: Optional[Iterable[Union[str, Path]]],
    *,
    default_root: Path,
) -> Tuple[Path, ...]:
    """归一化读取 `YAML` 文件的允许根目录(`allowed_yaml_roots`)策略.

    - 无论调用方是否显式提供,都会包含入口 `YAML` 的所在目录 `default_root`.
    - 所有根目录都必须存在且为目录(否则快速失败,避免静默误配置).
    - 返回去重后的绝对路径列表(稳定顺序,便于错误诊断比较).
    """
    roots_by_str: Dict[str, Path] = {}

    def _add_root(raw_root: Union[str, Path]) -> None:
        root = Path(str(raw_root)).expanduser().resolve(strict=False)
        if not root.exists() or not root.is_dir():
            msg = "allowed_yaml_roots must be existing directories: root='{}' | resolved='{}' | exists={} | is_dir={}".format(
                str(raw_root),
                str(root),
                bool(root.exists()),
                bool(root.is_dir()),
            )
            raise ValueError(msg)
        roots_by_str[str(root)] = root

    if allowed_yaml_roots is not None:
        for raw_root in allowed_yaml_roots:
            _add_root(raw_root)

    _add_root(default_root)

    return tuple(roots_by_str[key] for key in sorted(roots_by_str.keys()))


def validate_resolved_yaml_path_within_roots(
    *,
    raw_path: str,
    base_dir: Path,
    resolved_path: Path,
    allowed_yaml_roots: Sequence[Path],
    context_label: str,
) -> None:
    """校验 `resolved_path` 必须位于 `allowed_yaml_roots` 之一的目录树内."""
    for root in allowed_yaml_roots:
        if resolved_path == root or root in resolved_path.parents:
            return

    roots = ", ".join(str(r) for r in allowed_yaml_roots)
    msg = (
        "YAML path escapes allowed roots: context_label='{}' | raw_path='{}' | base_dir='{}' | resolved_path='{}' | allowed_yaml_roots=[{}]"
    ).format(
        str(context_label or ""),
        str(raw_path or ""),
        str(base_dir),
        str(resolved_path),
        roots,
    )
    raise ValueError(msg)
