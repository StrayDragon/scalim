"""`Book` `identity` 解析: 统一 `xlsx` 为唯一编写面 `SSOT`.

说明:
- `YAML` `SSOT`: `xlsx`(有 `path`=落盘; 无 `path`=内存总线)
- `xlsx_file` / `xlsx_memory` `YAML` 分支已移除: 出现即 `fail-fast` 并给出迁移提示
- 运行时身份以 `path` 有无(`pathful`/`pathless`)为 `SSOT`
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from ...init_var_nodes import OptionalPathNode
from ...schema_dsl.models import BookConfig

# 稳定子串 — 测试断言用(勿改语义)
REMOVED_XLSX_FILE_HINT = "xlsx_file was removed"
REMOVED_XLSX_MEMORY_HINT = "xlsx_memory was removed"
MIGRATE_TO_XLSX_PATH_HINT = "xlsx: {path:"
MIGRATE_TO_XLSX_EMPTY_HINT = "xlsx: {}"


def removed_xlsx_file_message(*, path: str) -> str:
    return f"{path}.xlsx_file was removed. Migration: use {path}.xlsx: {{path: <output_root>, allow_formulas?: false}}."


def removed_xlsx_memory_message(*, path: str, has_export: bool) -> str:
    if has_export:
        return f"{path}.xlsx_memory with export_xlsx was removed. Migration: use {path}.xlsx: {{path: <output_root>}}."
    return f"{path}.xlsx_memory was removed. Migration: use {path}.xlsx: {{}}."


def parse_book_config_mapping(
    cfg: dict[str, Any],
    *,
    path: str,
    parse_path_or_init_var: Callable[..., OptionalPathNode],
    raise_if_import_present: Callable[..., None],
    error_factory: Callable[..., BaseException],
) -> BookConfig:
    """解析 `books.<id>` `mapping` → `BookConfig`(身份由 `path` 有无决定)."""

    raise_if_import_present(cfg, path=path)

    if "write_lock" in cfg:
        msg = f"{path}.write_lock was removed; migrate to versioned outputs and locate results via <root>/manifest/latest.json"
        raise error_factory(msg, path=f"{path}.write_lock")

    if "kind" in cfg:
        kind = str(cfg.get("kind") or "").strip()
        if kind == "xlsx_file":
            msg = f"{path}.kind was removed. Migration: use {path}.xlsx: {{path: <output_root>}}."
        elif kind == "xlsx_memory":
            msg = f"{path}.kind was removed. Migration: use {path}.xlsx: {{}}."
        else:
            msg = f"{path}.kind was removed. Migration: use {path}.xlsx: {{path?: ...}}."
        raise error_factory(msg, path=f"{path}.kind")

    if "write_defaults" in cfg:
        msg = (
            f"{path}.write_defaults was removed from YAML authoring. "
            "Migration: configure BookWritePolicy via WorkflowRunOptions.resources_policy "
            "(Python SSOT; omit for builtin defaults)."
        )
        raise error_factory(msg, path=f"{path}.write_defaults")

    if "xlsx_file" in cfg:
        raise error_factory(removed_xlsx_file_message(path=path), path=f"{path}.xlsx_file")

    if "xlsx_memory" in cfg:
        mem_raw = cfg.get("xlsx_memory")
        has_export = isinstance(mem_raw, dict) and "export_xlsx" in mem_raw
        raise error_factory(
            removed_xlsx_memory_message(path=path, has_export=has_export),
            path=f"{path}.xlsx_memory",
        )

    allowed_keys = {"xlsx"}
    unknown = sorted({str(k) for k in cfg} - allowed_keys)
    if unknown:
        msg = "{} has unknown keys: {}".format(path, ", ".join(unknown))
        raise error_factory(msg, path=path)

    if "xlsx" not in cfg:
        msg = f"{path} must declare exactly one variant key: xlsx"
        raise error_factory(msg, path=path)

    return _parse_xlsx_branch(
        cfg,
        path=path,
        parse_path_or_init_var=parse_path_or_init_var,
        raise_if_import_present=raise_if_import_present,
        error_factory=error_factory,
    )


def _parse_xlsx_branch(
    cfg: dict[str, Any],
    *,
    path: str,
    parse_path_or_init_var: Callable[..., OptionalPathNode],
    raise_if_import_present: Callable[..., None],
    error_factory: Callable[..., BaseException],
) -> BookConfig:
    xlsx_raw = cfg.get("xlsx")
    if not isinstance(xlsx_raw, dict):
        msg = f"{path}.xlsx must be a mapping"
        raise error_factory(msg, path=f"{path}.xlsx")
    xlsx = cast("dict[str, Any]", xlsx_raw)  # pragma: allow-cast yaml mapping typed narrowing
    raise_if_import_present(xlsx, path=f"{path}.xlsx")

    if "export_xlsx" in xlsx:
        msg = f"{path}.xlsx.export_xlsx is not allowed; set {path}.xlsx.path for export (or use empty {path}.xlsx: {{}} for an in-memory bus)."  # noqa: E501
        raise error_factory(msg, path=f"{path}.xlsx.export_xlsx")
    if "write_defaults" in xlsx:
        msg = (
            f"{path}.xlsx.write_defaults was removed from YAML authoring. Migration: configure BookWritePolicy via Python ResourcesPolicy."
        )
        raise error_factory(msg, path=f"{path}.xlsx.write_defaults")
    if "budget" in xlsx:
        msg = (
            f"{path}.xlsx.budget was removed. Delete this field; book cell/sheet budget "
            "is no longer supported — rely on host resource limits for memory risk."
        )
        raise error_factory(msg, path=f"{path}.xlsx.budget")

    unknown_branch = sorted({str(k) for k in xlsx} - {"path", "allow_formulas"})
    if unknown_branch:
        msg = "{}.xlsx has unknown keys: {}".format(path, ", ".join(unknown_branch))
        raise error_factory(msg, path=f"{path}.xlsx")

    has_path_key = "path" in xlsx
    book_path = parse_path_or_init_var(xlsx.get("path"), path=f"{path}.xlsx.path") if has_path_key else None
    if has_path_key and (book_path is None or (isinstance(book_path, str) and not str(book_path).strip())):
        msg = f"{path}.xlsx.path must be a non-empty output root when provided"
        raise error_factory(msg, path=f"{path}.xlsx.path")
    if isinstance(book_path, str) and Path(book_path).suffix.lower() == ".xlsx":
        msg = (
            f"{path}.xlsx.path expects an output root directory, not a file path. "
            "Migration: set path to './out' and locate outputs via <root>/manifest/latest.json."
        )
        raise error_factory(msg, path=f"{path}.xlsx.path")

    allow_formulas_raw = xlsx.get("allow_formulas", True)
    if not isinstance(allow_formulas_raw, bool):
        msg = f"{path}.xlsx.allow_formulas must be a bool"
        raise error_factory(msg, path=f"{path}.xlsx.allow_formulas")

    if book_path is not None:
        return BookConfig(
            kind="",
            path=book_path,
            export_xlsx=None,
            allow_formulas=bool(allow_formulas_raw),
            write_defaults=None,
        )

    return BookConfig(
        kind="",
        path=None,
        export_xlsx=None,
        allow_formulas=False,
        write_defaults=None,
    )


__all__ = ()
