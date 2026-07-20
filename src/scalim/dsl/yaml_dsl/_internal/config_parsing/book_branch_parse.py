"""`Book` `identity` 解析: 统一 `xlsx` 唯一 authoring SSOT.

说明:
- YAML SSOT: `xlsx`(有 `path`=落盘; 无 `path`=内存总线)
- `xlsx_file` / `xlsx_memory` YAML 分支已移除: 出现 MUST fail-fast 并给出迁移提示
- 运行时身份以 `path` 有无(`pathful`/`pathless`)为 SSOT
"""

from pathlib import Path
from typing import Any, Callable, Dict, cast

from ...init_var_nodes import OptionalPathNode
from ...schema_dsl.models import BookConfig

# 稳定子串 — 测试断言用(勿改语义)
REMOVED_XLSX_FILE_HINT = "xlsx_file was removed"
REMOVED_XLSX_MEMORY_HINT = "xlsx_memory was removed"
MIGRATE_TO_XLSX_PATH_HINT = "xlsx: {path:"
MIGRATE_TO_XLSX_EMPTY_HINT = "xlsx: {}"


def removed_xlsx_file_message(*, path: str) -> str:
    return ("{}.xlsx_file was removed. Migration: use {}.xlsx: {{path: <output_root>, allow_formulas?: false}}.").format(path, path)


def removed_xlsx_memory_message(*, path: str, has_export: bool) -> str:
    if has_export:
        return ("{}.xlsx_memory with export_xlsx was removed. Migration: use {}.xlsx: {{path: <output_root>}}.").format(path, path)
    return ("{}.xlsx_memory was removed. Migration: use {}.xlsx: {{}}.").format(path, path)


def parse_book_config_mapping(
    cfg: Dict[str, Any],
    *,
    path: str,
    parse_path_or_init_var: Callable[..., OptionalPathNode],
    raise_if_import_present: Callable[..., None],
    error_factory: Callable[..., BaseException],
) -> BookConfig:
    """解析 `books.<id>` `mapping` → `BookConfig`(身份由 `path` 有无决定)."""

    raise_if_import_present(cfg, path=path)

    if "write_lock" in cfg:
        msg = "{}.write_lock was removed; migrate to versioned outputs and locate results via <root>/manifest/latest.json".format(path)
        raise error_factory(msg, path="{}.write_lock".format(path))

    if "kind" in cfg:
        kind = str(cfg.get("kind") or "").strip()
        if kind == "xlsx_file":
            msg = ("{}.kind was removed. Migration: use {}.xlsx: {{path: <output_root>}}.").format(path, path)
        elif kind == "xlsx_memory":
            msg = ("{}.kind was removed. Migration: use {}.xlsx: {{}}.").format(path, path)
        else:
            msg = ("{}.kind was removed. Migration: use {}.xlsx: {{path?: ...}}.").format(path, path)
        raise error_factory(msg, path="{}.kind".format(path))

    if "write_defaults" in cfg:
        msg = (
            "{}.write_defaults was removed from YAML authoring. "
            "Migration: configure BookWritePolicy via WorkflowRunOptions.resources_policy "
            "(Python SSOT; omit for builtin defaults)."
        ).format(path)
        raise error_factory(msg, path="{}.write_defaults".format(path))

    if "xlsx_file" in cfg:
        raise error_factory(removed_xlsx_file_message(path=path), path="{}.xlsx_file".format(path))

    if "xlsx_memory" in cfg:
        mem_raw = cfg.get("xlsx_memory")
        has_export = isinstance(mem_raw, dict) and "export_xlsx" in mem_raw
        raise error_factory(
            removed_xlsx_memory_message(path=path, has_export=has_export),
            path="{}.xlsx_memory".format(path),
        )

    allowed_keys = {"xlsx"}
    unknown = sorted({str(k) for k in cfg} - allowed_keys)
    if unknown:
        msg = "{} has unknown keys: {}".format(path, ", ".join(unknown))
        raise error_factory(msg, path=path)

    if "xlsx" not in cfg:
        msg = "{} must declare exactly one variant key: xlsx".format(path)
        raise error_factory(msg, path=path)

    return _parse_xlsx_branch(
        cfg,
        path=path,
        parse_path_or_init_var=parse_path_or_init_var,
        raise_if_import_present=raise_if_import_present,
        error_factory=error_factory,
    )


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
            kind="",
            path=book_path,
            budget=None,
            export_xlsx=None,
            allow_formulas=bool(allow_formulas_raw),
            write_defaults=None,
        )

    return BookConfig(
        kind="",
        path=None,
        budget=None,
        export_xlsx=None,
        allow_formulas=False,
        write_defaults=None,
    )


__all__ = ()
