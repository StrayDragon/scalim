import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union, cast

from .....vendor.compact.typing_extensionsx import TypeGuard
from .....vendor.dataclassesx import dataclass
from .error_envelope import ScalimYamlValidationError
from .yaml_load import load_yaml_mapping_text

__all__ = ()

_YAML_DSL_KIND_DEMAND = "demand"
_YAML_DSL_KIND_WORKFLOW = "workflow"
_YAML_DSL_KIND_CHOICES: Tuple[str, ...] = (
    _YAML_DSL_KIND_DEMAND,
    _YAML_DSL_KIND_WORKFLOW,
)

_IMPORT_ROOT_ALIAS_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


@dataclass(frozen=True)
class YamlDslLspKindOverride:
    glob: str
    kind: str


@dataclass(frozen=True)
class YamlDslLspConfig:
    python_roots: Tuple[Path, ...] = ()
    kind_overrides: Tuple[YamlDslLspKindOverride, ...] = ()


@dataclass(frozen=True)
class YamlDslImportRoot:
    path: Path
    alias: Optional[str] = None


@dataclass(frozen=True)
class YamlDslProjectConfig:
    """`scalim.yaml` 解析结果(仅承载 `YAML DSL` 相关配置)."""

    scalim_yaml_path: Path
    project_root: Path
    import_roots: Tuple[YamlDslImportRoot, ...]
    import_aliases: Mapping[str, Path]
    lsp: Optional[YamlDslLspConfig] = None


def _is_list(value: object) -> TypeGuard[List[object]]:
    return isinstance(value, list)


def _read_yaml_mapping(path: Path) -> Dict[str, Any]:
    try:
        loaded, _locations, _lines = load_yaml_mapping_text(
            path.read_text(encoding="utf-8"),
            source_path=str(path),
            detect_duplicate_keys=True,
        )
    except ScalimYamlValidationError as exc:
        for envelope in exc.errors:
            if str(envelope.code) == "yaml_empty_document":
                return {}
        msg = "scalim.yaml parse error: path='{}'".format(str(path))
        if exc.errors:
            msg = "{}: {}".format(msg, exc.errors[0].message)
        raise TypeError(msg) from None

    if not isinstance(loaded, dict):
        msg = "scalim.yaml must be a mapping: path='{}'".format(str(path))
        raise TypeError(msg)
    return loaded


def _resolve_dir(value: object, *, base_dir: Path, context_label: str) -> Path:
    raw = str(value or "")
    if not raw.strip():
        msg = "{} must be a non-empty directory path".format(str(context_label or "path"))
        raise TypeError(msg)
    resolved = (base_dir / raw).expanduser().resolve(strict=False)
    try:
        _ = resolved.relative_to(base_dir)
    except Exception:  # noqa: BLE001
        msg = "{} must stay within project_root: raw='{}' | project_root='{}' | resolved='{}'".format(
            str(context_label or "path"),
            raw,
            str(base_dir),
            str(resolved),
        )
        raise ValueError(msg) from None
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


def _resolve_dir_allow_external(value: object, *, base_dir: Path, context_label: str) -> Path:
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


def _parse_yaml_dsl_dict(raw: Mapping[str, Any], *, scalim_yaml_path: Path) -> Dict[str, Any]:
    yaml_dsl = raw.get("yaml_dsl")
    if yaml_dsl is None:
        return {}
    if isinstance(yaml_dsl, dict):
        return cast("Dict[str, Any]", yaml_dsl)  # pragma: allow-cast yaml mapping typed narrowing
    msg = "scalim.yaml yaml_dsl must be a mapping: path='{}'".format(str(scalim_yaml_path))
    raise TypeError(msg)


def _parse_import_roots(
    yaml_dsl_dict: Dict[str, Any],
    *,
    project_root: Path,
    scalim_yaml_path: Path,
) -> Tuple[Tuple[YamlDslImportRoot, ...], Dict[str, Path]]:
    raw_roots = yaml_dsl_dict.get("import_roots")
    if raw_roots is None:
        return (), {}
    if not _is_list(raw_roots):
        msg = "scalim.yaml yaml_dsl.import_roots must be a list: path='{}'".format(str(scalim_yaml_path))
        raise TypeError(msg)

    import_roots: List[YamlDslImportRoot] = []
    import_aliases: Dict[str, Path] = {}

    for idx, raw_item in enumerate(raw_roots):
        item_path = "yaml_dsl.import_roots[{}]".format(idx)
        if not isinstance(raw_item, dict):
            msg = "scalim.yaml {} must be a mapping: path='{}'".format(item_path, str(scalim_yaml_path))
            raise TypeError(msg)
        item = cast("Dict[str, Any]", raw_item)  # pragma: allow-cast yaml mapping typed narrowing
        unknown = sorted({str(k) for k in item} - {"path", "alias"})
        if unknown:
            msg = "scalim.yaml {} has unknown keys: {}: path='{}'".format(item_path, ", ".join(unknown), str(scalim_yaml_path))
            raise TypeError(msg)

        raw_dir = item.get("path")
        dir_path = _resolve_dir(raw_dir, base_dir=project_root, context_label="{}.path".format(item_path))

        raw_alias = item.get("alias")
        alias: Optional[str] = None
        if raw_alias is not None:
            if not isinstance(raw_alias, str) or not raw_alias.strip():
                msg = "scalim.yaml {}.alias must be a non-empty string: path='{}'".format(item_path, str(scalim_yaml_path))
                raise TypeError(msg)
            alias = str(raw_alias).strip()
            if alias != "@" and not _IMPORT_ROOT_ALIAS_RE.match(alias):
                msg = "scalim.yaml {}.alias must be '@' or match {}: got={!r}: path='{}'".format(
                    item_path,
                    _IMPORT_ROOT_ALIAS_RE.pattern,
                    alias,
                    str(scalim_yaml_path),
                )
                raise ValueError(msg)
            if alias in import_aliases:
                msg = "scalim.yaml yaml_dsl.import_roots alias must be unique: alias={!r}: path='{}'".format(alias, str(scalim_yaml_path))
                raise ValueError(msg)
            import_aliases[alias] = dir_path

        import_roots.append(YamlDslImportRoot(path=dir_path, alias=alias))

    return tuple(import_roots), import_aliases


def _parse_lsp_python_roots(lsp_dict: Dict[str, Any], *, project_root: Path, scalim_yaml_path: Path) -> Tuple[Path, ...]:
    raw_python_roots = lsp_dict.get("python_roots")
    if raw_python_roots is None:
        return ()
    if not _is_list(raw_python_roots):
        msg = "scalim.yaml yaml_dsl.lsp.python_roots must be a list: path='{}'".format(str(scalim_yaml_path))
        raise TypeError(msg)

    resolved_py_roots: List[Path] = []
    for idx, raw_root in enumerate(raw_python_roots):
        resolved_py_roots.append(
            _resolve_dir_allow_external(raw_root, base_dir=project_root, context_label="yaml_dsl.lsp.python_roots[{}]".format(idx))
        )
    return tuple(resolved_py_roots)


def _parse_lsp_kind_overrides(lsp_dict: Dict[str, Any], *, scalim_yaml_path: Path) -> Tuple[YamlDslLspKindOverride, ...]:
    raw_kind_overrides = lsp_dict.get("kind_overrides")
    if raw_kind_overrides is None:
        return ()
    if not _is_list(raw_kind_overrides):
        msg = "scalim.yaml yaml_dsl.lsp.kind_overrides must be a list: path='{}'".format(str(scalim_yaml_path))
        raise TypeError(msg)

    overrides: List[YamlDslLspKindOverride] = []
    for idx, item in enumerate(raw_kind_overrides):
        item_path = "yaml_dsl.lsp.kind_overrides[{}]".format(idx)
        if not isinstance(item, dict):
            msg = "scalim.yaml {} must be a mapping: path='{}'".format(item_path, str(scalim_yaml_path))
            raise TypeError(msg)
        item_dict = cast("Dict[str, Any]", item)  # pragma: allow-cast yaml mapping typed narrowing

        unknown = sorted({str(k) for k in item_dict} - {"glob", "kind"})
        if unknown:
            msg = "scalim.yaml {} has unknown keys: {}: path='{}'".format(item_path, ", ".join(unknown), str(scalim_yaml_path))
            raise TypeError(msg)

        glob_raw = item_dict.get("glob")
        glob = str(glob_raw or "").strip() if isinstance(glob_raw, str) else ""
        if not glob:
            msg = "scalim.yaml {}.glob must be a non-empty string: path='{}'".format(item_path, str(scalim_yaml_path))
            raise TypeError(msg)

        kind_raw = item_dict.get("kind")
        kind = str(kind_raw or "").strip().lower() if isinstance(kind_raw, str) else ""
        if kind not in _YAML_DSL_KIND_CHOICES:
            allowed = ", ".join(_YAML_DSL_KIND_CHOICES)
            msg = "scalim.yaml {}.kind must be one of {}: path='{}'".format(
                item_path,
                allowed,
                str(scalim_yaml_path),
            )
            raise ValueError(msg)

        overrides.append(YamlDslLspKindOverride(glob=glob, kind=kind))

    return tuple(overrides)


def _parse_lsp_config(yaml_dsl_dict: Dict[str, Any], *, project_root: Path, scalim_yaml_path: Path) -> Optional[YamlDslLspConfig]:
    raw_lsp = yaml_dsl_dict.get("lsp")
    if raw_lsp is None:
        return None
    if not isinstance(raw_lsp, dict):
        msg = "scalim.yaml yaml_dsl.lsp must be a mapping: path='{}'".format(str(scalim_yaml_path))
        raise TypeError(msg)

    lsp_dict = cast("Dict[str, Any]", raw_lsp)  # pragma: allow-cast yaml mapping typed narrowing
    unknown = sorted({str(k) for k in lsp_dict} - {"python_roots", "kind_overrides"})
    if unknown:
        msg = "scalim.yaml yaml_dsl.lsp has unknown keys: {}: path='{}'".format(", ".join(unknown), str(scalim_yaml_path))
        raise TypeError(msg)

    python_roots = _parse_lsp_python_roots(lsp_dict, project_root=project_root, scalim_yaml_path=scalim_yaml_path)
    kind_overrides = _parse_lsp_kind_overrides(lsp_dict, scalim_yaml_path=scalim_yaml_path)
    return YamlDslLspConfig(python_roots=python_roots, kind_overrides=kind_overrides)


def _parse_yaml_dsl_section(raw: Mapping[str, Any], *, scalim_yaml_path: Path) -> YamlDslProjectConfig:
    project_root = scalim_yaml_path.parent
    yaml_dsl_dict = _parse_yaml_dsl_dict(raw, scalim_yaml_path=scalim_yaml_path)
    unknown_yaml_dsl_keys = sorted({str(k) for k in yaml_dsl_dict} - {"import_roots", "lsp"})
    if unknown_yaml_dsl_keys:
        msg = "scalim.yaml yaml_dsl has unknown keys: {}: path='{}'".format(
            ", ".join(unknown_yaml_dsl_keys),
            str(scalim_yaml_path),
        )
        raise TypeError(msg)
    import_roots, import_aliases = _parse_import_roots(yaml_dsl_dict, project_root=project_root, scalim_yaml_path=scalim_yaml_path)
    lsp = _parse_lsp_config(yaml_dsl_dict, project_root=project_root, scalim_yaml_path=scalim_yaml_path)

    return YamlDslProjectConfig(
        scalim_yaml_path=scalim_yaml_path,
        project_root=project_root,
        import_roots=import_roots,
        import_aliases=import_aliases,
        lsp=lsp,
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
