"""`Book` `identity` 解析: 统一 `xlsx` + `deprecated` 别名正规化.

说明:
- 新 `SSOT`: `xlsx`(有 `path`=落盘; 无 `path`=内存总线)
- 过渡期别名: `xlsx_file` / `xlsx_memory` → 正规化为同一 `BookConfig`(身份由 `path` 有无决定)
- `kind=xlsx_file|xlsx_memory` 仅作 `deprecated` `wire` `shim`(见 `book_identity.legacy_kind_shim`)
- 旧别名 `MUST` 触发 `DeprecationWarning`(稳定文案 `SSOT` 在本模块)
"""

import warnings
from pathlib import Path
from typing import Any, Callable, Dict, Tuple, cast

from ...init_var_nodes import OptionalPathNode
from ...schema_dsl.models import BookConfig, BookExportXlsxConfig

# 稳定子串 — 测试断言用(勿改语义)
DEPRECATED_XLSX_FILE_HINT = "deprecated; migrate to"
DEPRECATED_XLSX_TO_PATH_HINT = "xlsx: {path:"
DEPRECATED_XLSX_EMPTY_HINT = "xlsx: {}"
DEPRECATED_XLSX_MEMORY_HINT = "deprecated; migrate to"


def warn_deprecated_xlsx_file(*, path: str) -> None:
    msg = ("{}.xlsx_file is deprecated; migrate to {}.xlsx: {{path: <output_root>, allow_formulas?: false}}.").format(path, path)
    warnings.warn(msg, DeprecationWarning, stacklevel=3)


def warn_deprecated_xlsx_memory(*, path: str, has_export: bool) -> None:
    if has_export:
        msg = ("{}.xlsx_memory with export_xlsx is deprecated; migrate to {}.xlsx: {{path: <output_root>}}.").format(path, path)
    else:
        msg = ("{}.xlsx_memory is deprecated; migrate to {}.xlsx: {{}}.").format(path, path)
    warnings.warn(msg, DeprecationWarning, stacklevel=3)


def deprecated_book_branch_validation_message(*, book_path: str, branch: str) -> str:
    """供 `validate` 报告使用的 `warning` 文案(与 `DeprecationWarning` 对齐)."""

    if branch == "xlsx_file":
        return ("{}.xlsx_file is deprecated; migrate to {}.xlsx: {{path: <output_root>, allow_formulas?: false}}.").format(
            book_path, book_path
        )
    if branch == "xlsx_memory_export":
        return ("{}.xlsx_memory with export_xlsx is deprecated; migrate to {}.xlsx: {{path: <output_root>}}.").format(book_path, book_path)
    return ("{}.xlsx_memory is deprecated; migrate to {}.xlsx: {{}}.").format(book_path, book_path)


def parse_book_config_mapping(
    cfg: Dict[str, Any],
    *,
    path: str,
    parse_path_or_init_var: Callable[..., OptionalPathNode],
    parse_export_xlsx: Callable[..., BookExportXlsxConfig],
    raise_if_import_present: Callable[..., None],
    error_factory: Callable[..., BaseException],
) -> BookConfig:
    """解析 `books.<id>` `mapping` → `BookConfig`(内部 `kind` 仍为 `xlsx_file|xlsx_memory`)."""

    raise_if_import_present(cfg, path=path)

    if "write_lock" in cfg:
        msg = "{}.write_lock was removed; migrate to versioned outputs and locate results via <root>/manifest/latest.json".format(path)
        raise error_factory(msg, path="{}.write_lock".format(path))

    if "kind" in cfg:
        kind = str(cfg.get("kind") or "").strip()
        if kind == "xlsx_file":
            msg = ("{}.kind was removed. Migration: use {}.xlsx: {{path: <output_root>}} (or deprecated {}.xlsx_file: {{...}}).").format(
                path, path, path
            )
        elif kind == "xlsx_memory":
            msg = ("{}.kind was removed. Migration: use {}.xlsx: {{}} (or deprecated {}.xlsx_memory: {{...}}).").format(path, path, path)
        else:
            msg = ("{}.kind was removed. Migration: use {}.xlsx: {{path?: ...}} (deprecated aliases: xlsx_file / xlsx_memory).").format(
                path, path
            )
        raise error_factory(msg, path="{}.kind".format(path))

    if "write_defaults" in cfg:
        msg = (
            "{}.write_defaults was removed from YAML authoring. "
            "Migration: configure BookWritePolicy via WorkflowRunOptions.resources_policy "
            "(Python SSOT; omit for builtin defaults)."
        ).format(path)
        raise error_factory(msg, path="{}.write_defaults".format(path))

    allowed_keys = {"xlsx", "xlsx_file", "xlsx_memory"}
    unknown = sorted({str(k) for k in cfg} - allowed_keys)
    if unknown:
        msg = "{} has unknown keys: {}".format(path, ", ".join(unknown))
        raise error_factory(msg, path=path)

    present = [k for k in ("xlsx", "xlsx_file", "xlsx_memory") if k in cfg]
    if len(present) != 1:
        msg = "{} must choose exactly one variant key: xlsx (preferred) or deprecated xlsx_file / xlsx_memory".format(path)
        raise error_factory(msg, path=path)

    branch = present[0]

    if branch == "xlsx":
        return _parse_xlsx_branch(
            cfg,
            path=path,
            parse_path_or_init_var=parse_path_or_init_var,
            raise_if_import_present=raise_if_import_present,
            error_factory=error_factory,
        )

    if branch == "xlsx_file":
        book = _parse_xlsx_file_branch(
            cfg,
            path=path,
            parse_path_or_init_var=parse_path_or_init_var,
            raise_if_import_present=raise_if_import_present,
            error_factory=error_factory,
        )
        warn_deprecated_xlsx_file(path=path)
        return book

    book, has_export = _parse_xlsx_memory_branch(
        cfg,
        path=path,
        parse_export_xlsx=parse_export_xlsx,
        raise_if_import_present=raise_if_import_present,
        error_factory=error_factory,
    )
    warn_deprecated_xlsx_memory(path=path, has_export=has_export)
    return book


def _parse_xlsx_branch(
    cfg: Dict[str, Any],
    *,
    path: str,
    parse_path_or_init_var: Callable[..., OptionalPathNode],
    raise_if_import_present: Callable[..., None],
    error_factory: Callable[..., BaseException],
) -> BookConfig:
    xlsx_raw = cfg.get("xlsx")
    if not isinstance(xlsx_raw, dict):
        msg = "{}.xlsx must be a mapping".format(path)
        raise error_factory(msg, path="{}.xlsx".format(path))
    xlsx = cast("Dict[str, Any]", xlsx_raw)  # pragma: allow-cast yaml mapping typed narrowing
    raise_if_import_present(xlsx, path="{}.xlsx".format(path))

    if "export_xlsx" in xlsx:
        msg = ("{}.xlsx.export_xlsx is not allowed; set {}.xlsx.path for export (or use empty {}.xlsx: {{}} for an in-memory bus).").format(
            path, path, path
        )
        raise error_factory(msg, path="{}.xlsx.export_xlsx".format(path))
    if "write_defaults" in xlsx:
        msg = (
            "{}.xlsx.write_defaults was removed from YAML authoring. Migration: configure BookWritePolicy via Python ResourcesPolicy."
        ).format(path)
        raise error_factory(msg, path="{}.xlsx.write_defaults".format(path))
    if "budget" in xlsx:
        msg = ("{}.xlsx.budget was removed from YAML authoring. Migration: configure BookBudgetPolicy via Python ResourcesPolicy.").format(
            path
        )
        raise error_factory(msg, path="{}.xlsx.budget".format(path))

    unknown_branch = sorted({str(k) for k in xlsx} - {"path", "allow_formulas"})
    if unknown_branch:
        msg = "{}.xlsx has unknown keys: {}".format(path, ", ".join(unknown_branch))
        raise error_factory(msg, path="{}.xlsx".format(path))

    has_path_key = "path" in xlsx
    book_path = parse_path_or_init_var(xlsx.get("path"), path="{}.xlsx.path".format(path)) if has_path_key else None
    if has_path_key and (book_path is None or (isinstance(book_path, str) and not str(book_path).strip())):
        msg = "{}.xlsx.path must be a non-empty output root when provided".format(path)
        raise error_factory(msg, path="{}.xlsx.path".format(path))
    if isinstance(book_path, str) and Path(book_path).suffix.lower() == ".xlsx":
        msg = (
            "{}.xlsx.path expects an output root directory, not a file path. "
            "Migration: set path to './out' and locate outputs via <root>/manifest/latest.json."
        ).format(path)
        raise error_factory(msg, path="{}.xlsx.path".format(path))

    allow_formulas_raw = xlsx.get("allow_formulas", True)
    if not isinstance(allow_formulas_raw, bool):
        msg = "{}.xlsx.allow_formulas must be a bool".format(path)
        raise error_factory(msg, path="{}.xlsx.allow_formulas".format(path))

    if book_path is not None:
        return BookConfig(
            kind="xlsx_file",
            path=book_path,
            budget=None,
            export_xlsx=None,
            allow_formulas=bool(allow_formulas_raw),
            write_defaults=None,
        )

    return BookConfig(
        kind="xlsx_memory",
        path=None,
        budget=None,
        export_xlsx=None,
        allow_formulas=False,
        write_defaults=None,
    )


def _parse_xlsx_file_branch(
    cfg: Dict[str, Any],
    *,
    path: str,
    parse_path_or_init_var: Callable[..., OptionalPathNode],
    raise_if_import_present: Callable[..., None],
    error_factory: Callable[..., BaseException],
) -> BookConfig:
    xlsx_file_raw = cfg.get("xlsx_file")
    if not isinstance(xlsx_file_raw, dict):
        msg = "{}.xlsx_file must be a mapping".format(path)
        raise error_factory(msg, path="{}.xlsx_file".format(path))
    xlsx_file = cast("Dict[str, Any]", xlsx_file_raw)  # pragma: allow-cast yaml mapping typed narrowing
    raise_if_import_present(xlsx_file, path="{}.xlsx_file".format(path))
    unknown_branch = sorted({str(k) for k in xlsx_file} - {"path", "allow_formulas"})
    if unknown_branch:
        if "write_lock" in unknown_branch:
            msg = (
                "{}.xlsx_file.write_lock was removed; migrate to versioned outputs and locate results via <root>/manifest/latest.json"
            ).format(path)
            raise error_factory(msg, path="{}.xlsx_file.write_lock".format(path))
        msg = "{}.xlsx_file has unknown keys: {}".format(path, ", ".join(unknown_branch))
        raise error_factory(msg, path="{}.xlsx_file".format(path))

    book_path = parse_path_or_init_var(xlsx_file.get("path"), path="{}.xlsx_file.path".format(path))
    if not book_path or (isinstance(book_path, str) and not book_path.strip()):
        msg = "{}.xlsx_file.path is required".format(path)
        raise error_factory(msg, path="{}.xlsx_file.path".format(path))
    if isinstance(book_path, str) and Path(book_path).suffix.lower() == ".xlsx":
        msg = (
            "{}.xlsx_file.path now expects an output root directory, not a file path. "
            "Migration: set path to './out' and locate outputs via <root>/manifest/latest.json."
        ).format(path)
        raise error_factory(msg, path="{}.xlsx_file.path".format(path))

    allow_formulas_raw = xlsx_file.get("allow_formulas", True)
    if not isinstance(allow_formulas_raw, bool):
        msg = "{}.xlsx_file.allow_formulas must be a bool".format(path)
        raise error_factory(msg, path="{}.xlsx_file.allow_formulas".format(path))

    return BookConfig(
        kind="xlsx_file",
        path=book_path,
        budget=None,
        export_xlsx=None,
        allow_formulas=bool(allow_formulas_raw),
        write_defaults=None,
    )


def _parse_xlsx_memory_branch(
    cfg: Dict[str, Any],
    *,
    path: str,
    parse_export_xlsx: Callable[..., BookExportXlsxConfig],
    raise_if_import_present: Callable[..., None],
    error_factory: Callable[..., BaseException],
) -> Tuple[BookConfig, bool]:
    xlsx_memory_raw = cfg.get("xlsx_memory")
    if not isinstance(xlsx_memory_raw, dict):
        msg = "{}.xlsx_memory must be a mapping".format(path)
        raise error_factory(msg, path="{}.xlsx_memory".format(path))
    xlsx_memory = cast("Dict[str, Any]", xlsx_memory_raw)  # pragma: allow-cast yaml mapping typed narrowing
    raise_if_import_present(xlsx_memory, path="{}.xlsx_memory".format(path))
    if "budget" in xlsx_memory:
        msg = (
            "{}.xlsx_memory.budget was removed from YAML authoring. "
            "Migration: configure BookBudgetPolicy via WorkflowRunOptions.resources_policy "
            "(Python SSOT; omit for unlimited)."
        ).format(path)
        raise error_factory(msg, path="{}.xlsx_memory.budget".format(path))
    unknown_branch = sorted({str(k) for k in xlsx_memory} - {"export_xlsx"})
    if unknown_branch:
        if "write_lock" in unknown_branch:
            msg = (
                "{}.xlsx_memory.write_lock was removed; migrate to versioned outputs and locate results via <root>/manifest/latest.json"
            ).format(path)
            raise error_factory(msg, path="{}.xlsx_memory.write_lock".format(path))
        msg = "{}.xlsx_memory has unknown keys: {}".format(path, ", ".join(unknown_branch))
        raise error_factory(msg, path="{}.xlsx_memory".format(path))

    has_export = "export_xlsx" in xlsx_memory
    export_cfg = parse_export_xlsx(xlsx_memory.get("export_xlsx"), path="{}.xlsx_memory.export_xlsx".format(path)) if has_export else None

    if export_cfg is not None and export_cfg.path is not None:
        return (
            BookConfig(
                kind="xlsx_file",
                path=export_cfg.path,
                budget=None,
                export_xlsx=None,
                allow_formulas=bool(export_cfg.allow_formulas),
                write_defaults=None,
            ),
            True,
        )

    return (
        BookConfig(
            kind="xlsx_memory",
            path=None,
            budget=None,
            export_xlsx=export_cfg,
            allow_formulas=False,
            write_defaults=None,
        ),
        has_export,
    )


__all__ = ()
