# pragma: allow-c901-file plan: c75
"""`workflow` 编译阶段实现(内部模块).

说明:
- 承载 `workflow config` -> `workflow IR` 的编译逻辑
- 运行时需兼容 `Python 3.6`
"""

import math
import os
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple, cast

from ...spec.ir._workflow import (
    AppendSheetNodeIr,
    WorkflowAnyNodeIr,
    WorkflowArtifactsIr,
    WorkflowCachePoolBudgetIr,
    WorkflowCachePoolIr,
    WorkflowCachePoolPinIr,
    WorkflowCtxOptionsIr,
    WorkflowEdgeIr,
    WorkflowIr,
    WorkflowNodeIr,
    WorkflowNodeType,
    WorkflowOptionsIr,
    WorkflowOutputStagingOptionsIr,
    WorkflowResourceIr,
    WorkflowResourcesWaitDiagnosticsIr,
    WorkflowResourcesWaitOptionsIr,
    WriteSheetNodeIr,
)
from ...vendor.dataclassesx import dataclass, replace
from ._internal.config_parsing.loader import YamlDemandLoader
from ._internal.config_parsing.template_precompile import DEFAULT_RENDERED_YAML_MAX_LEN
from ._internal.patch_apply import (
    as_bool as _patch_as_bool,
)
from ._internal.patch_apply import (
    as_opt_mapping as _patch_as_opt_mapping,
)
from ._internal.patch_apply import (
    as_opt_str as _patch_as_opt_str,
)
from ._internal.patch_apply import (
    as_required_non_empty_str as _patch_as_required_non_empty_str,
)
from ._internal.patch_apply import (
    assert_no_unknown_keys as _patch_assert_no_unknown_keys,
)
from ._internal.validation_contracts import validate_excel_sheet_name as _validate_excel_sheet_name_ssot
from .runtime.contracts import (
    BookResourceOverride,
    FileResourceOverride,
    OutputExtraSheetOverride,
    OutputExtrasOverride,
    OutputOverride,
    OutputsDefaultsOverride,
    OutputToOverride,
    OutputWriteOverride,
    ResourcesOverride,
    RunOverrides,
)
from .runtime.output_path_resolve import resolve_yaml_relative_output_path
from .schema_dsl.constants import DEFAULT_OUTPUT_ENCODING
from .schema_dsl.models import (
    BookBudgetConfig,
    BookConfig,
    BookExportXlsxConfig,
    BookWriteDefaultsConfig,
    DemandConfig,
    FileConfig,
    OutputExtraSheetConfig,
    OutputTargetConfig,
    OutputToConfig,
    OutputWriteConfig,
)
from .schema_dsl.output_enums import (
    BOOK_WRITE_ALIGN_BY_ENUM,
    BOOK_WRITE_HEADER_POLICY_ENUM,
    BOOK_WRITE_MODE_ENUM,
    BOOK_WRITE_ON_CONFLICT_ENUM,
    BOOK_WRITE_ON_MISMATCH_ENUM,
    DEFAULT_BOOK_WRITE_ALIGN_BY,
    DEFAULT_BOOK_WRITE_HEADER_POLICY,
    DEFAULT_BOOK_WRITE_MODE,
    DEFAULT_BOOK_WRITE_ON_CONFLICT,
    DEFAULT_BOOK_WRITE_ON_MISMATCH,
    FILE_KINDS,
)
from .workflow import ScalimWorkflowConfigError, WorkflowConfig, resolve_workflow_demand_path
from .workflow_config._models import (
    WorkflowCachePoolOptions,
    WorkflowCtxOptions,
    WorkflowOutputStagingOptions,
    WorkflowResourcesWaitDiagnosticsOptions,
    WorkflowResourcesWaitOptions,
)


@dataclass(frozen=True)
class WorkflowCompileResult:
    workflow_ir: WorkflowIr
    demand_configs_by_run_id: Dict[str, DemandConfig]


_INTERNAL_NODE_ID_PREFIX = "__wf__"


def _as_abs_path(raw_path: str) -> str:
    return str(Path(str(raw_path)).expanduser().resolve(strict=False))


def _try_resolve_book_export_abs_path(
    book: BookConfig,
    *,
    book_id: str,
    base_dir: str,
    init_vars: Optional[Dict[str, object]],
    path_prefix: str,
) -> Optional[str]:
    try:
        export_path, _opts = _book_export_path_and_options(
            book,
            book_id=str(book_id),
            base_dir=str(base_dir),
            init_vars=init_vars,
            path_prefix=str(path_prefix),
        )
    except (TypeError, ValueError):
        return None
    if not export_path:
        return None
    return _as_abs_path(str(export_path))


def _validate_excel_sheet_name(sheet: str, *, path: str) -> None:
    _validate_excel_sheet_name_ssot(str(sheet), path=str(path))


def _workflow_base_dir(workflow_yaml_path: str) -> Path:
    wf_path = Path(str(workflow_yaml_path or "")).expanduser().resolve(strict=False)
    return wf_path.parent


def _demand_base_dir(demand_yaml_path: str) -> Path:
    p = Path(str(demand_yaml_path or "")).expanduser().resolve(strict=False)
    return p.parent


def _outputs_path_ref(outputs_path: str, idx: int, suffix: str) -> str:
    return "{}.{}.{}".format(str(outputs_path), int(idx), suffix)


def _effective_book_binding_for_output(
    out_cfg: OutputTargetConfig,
    *,
    idx: int,
    outputs_path: str,
) -> Tuple[Optional[str], str]:
    to_cfg = out_cfg.to
    if to_cfg is not None and to_cfg.book is not None:
        book = str(to_cfg.book or "").strip()
        if book:
            return book, _outputs_path_ref(outputs_path, int(idx), "to.book")

    return None, _outputs_path_ref(outputs_path, int(idx), "to.book")


def _effective_file_binding_for_output(
    out_cfg: OutputTargetConfig,
    *,
    idx: int,
    outputs_path: str,
) -> Tuple[Optional[str], str]:
    to_cfg = out_cfg.to
    if to_cfg is not None and to_cfg.file is not None:
        file_id = str(to_cfg.file or "").strip()
        if file_id:
            return file_id, _outputs_path_ref(outputs_path, int(idx), "to.file")

    return None, _outputs_path_ref(outputs_path, int(idx), "to.file")


def _effective_sheet_name_for_output(out_cfg: OutputTargetConfig, *, idx: int, outputs_path: str) -> Tuple[str, str]:
    to_cfg = out_cfg.to
    if to_cfg is not None and to_cfg.sheet is not None:
        return str(to_cfg.sheet or "").strip(), _outputs_path_ref(outputs_path, int(idx), "to.sheet")
    return str(out_cfg.name or ""), _outputs_path_ref(outputs_path, int(idx), "name")


def _effective_write_defaults(book: BookConfig) -> BookWriteDefaultsConfig:
    base = book.write_defaults
    if base is not None:
        return base
    return BookWriteDefaultsConfig(
        mode=str(DEFAULT_BOOK_WRITE_MODE),
        align_by=str(DEFAULT_BOOK_WRITE_ALIGN_BY),
        header_policy=str(DEFAULT_BOOK_WRITE_HEADER_POLICY),
        on_mismatch=str(DEFAULT_BOOK_WRITE_ON_MISMATCH),
        on_conflict=str(DEFAULT_BOOK_WRITE_ON_CONFLICT),
    )


def _validate_book_write_defaults_enum(value: str, *, key: str, allowed: Sequence[str], path: str) -> None:
    if value in allowed:
        return
    msg = "Invalid write_defaults.{}={!r}; expected one of: {}".format(str(key), value, ", ".join(allowed))
    raise ScalimWorkflowConfigError(msg, path=path)


def _overlay_book_write_defaults_patch(
    base: BookWriteDefaultsConfig,
    patch: Dict[str, Any],
    *,
    path: str,
) -> BookWriteDefaultsConfig:
    allowed_keys = {"mode", "align_by", "header_policy", "on_mismatch", "on_conflict"}
    _patch_assert_no_unknown_keys(patch, allowed_keys=allowed_keys, path=path)

    mode = str(base.mode or DEFAULT_BOOK_WRITE_MODE)
    align_by = str(base.align_by or DEFAULT_BOOK_WRITE_ALIGN_BY)
    header_policy = str(base.header_policy or DEFAULT_BOOK_WRITE_HEADER_POLICY)
    on_mismatch = str(base.on_mismatch or DEFAULT_BOOK_WRITE_ON_MISMATCH)
    on_conflict = str(base.on_conflict or DEFAULT_BOOK_WRITE_ON_CONFLICT)

    raw_mode = _patch_as_opt_str(patch.get("mode"), path="{}.mode".format(path))
    raw_align_by = _patch_as_opt_str(patch.get("align_by"), path="{}.align_by".format(path))
    raw_header_policy = _patch_as_opt_str(patch.get("header_policy"), path="{}.header_policy".format(path))
    raw_on_mismatch = _patch_as_opt_str(patch.get("on_mismatch"), path="{}.on_mismatch".format(path))
    raw_on_conflict = _patch_as_opt_str(patch.get("on_conflict"), path="{}.on_conflict".format(path))

    if raw_mode is not None:
        mode = raw_mode
    if raw_align_by is not None:
        align_by = raw_align_by
    if raw_header_policy is not None:
        header_policy = raw_header_policy
    if raw_on_mismatch is not None:
        on_mismatch = raw_on_mismatch
    if raw_on_conflict is not None:
        on_conflict = raw_on_conflict

    _validate_book_write_defaults_enum(
        str(mode),
        key="mode",
        allowed=BOOK_WRITE_MODE_ENUM,
        path="{}.mode".format(path),
    )
    _validate_book_write_defaults_enum(
        str(align_by),
        key="align_by",
        allowed=BOOK_WRITE_ALIGN_BY_ENUM,
        path="{}.align_by".format(path),
    )
    _validate_book_write_defaults_enum(
        str(header_policy),
        key="header_policy",
        allowed=BOOK_WRITE_HEADER_POLICY_ENUM,
        path="{}.header_policy".format(path),
    )
    _validate_book_write_defaults_enum(
        str(on_mismatch),
        key="on_mismatch",
        allowed=BOOK_WRITE_ON_MISMATCH_ENUM,
        path="{}.on_mismatch".format(path),
    )
    _validate_book_write_defaults_enum(
        str(on_conflict),
        key="on_conflict",
        allowed=BOOK_WRITE_ON_CONFLICT_ENUM,
        path="{}.on_conflict".format(path),
    )

    return BookWriteDefaultsConfig(
        mode=str(mode),
        align_by=str(align_by),
        header_policy=str(header_policy),
        on_mismatch=str(on_mismatch),
        on_conflict=str(on_conflict),
    )


def _validate_xlsx_memory_align_by(
    *,
    book: BookConfig,
    book_id: str,
) -> None:
    if str(book.kind or "").strip() != "xlsx_memory":
        return

    effective_defaults = _effective_write_defaults(book)
    if str(effective_defaults.mode or DEFAULT_BOOK_WRITE_MODE) != "append":
        return
    if str(effective_defaults.align_by or "") != "header":
        return

    align_by_path = "resources.books.{}.write_defaults.align_by".format(str(book_id))
    msg = (
        "books.kind=xlsx_memory does not support write_defaults.align_by=header; "
        "internal rows only use canonical field keys. Migrate to resources.books.<book_id>.write_defaults.align_by=field_id "
        "and keep write.header_fields_output_by for export display (book_id={!r})"
    ).format(str(book_id))
    raise ScalimWorkflowConfigError(msg, path=str(align_by_path))


def _apply_book_budget_patch(budget: Optional[BookBudgetConfig], raw: Dict[str, Any], *, path: str) -> BookBudgetConfig:
    max_sheets_raw = raw.get("max_sheets")
    max_total_cells_raw = raw.get("max_total_cells")

    if budget is None:
        if max_sheets_raw is None or max_total_cells_raw is None:
            msg = "{}.budget requires max_sheets and max_total_cells when creating a new xlsx_memory book".format(path)
            raise ScalimWorkflowConfigError(msg, path="{}.budget".format(path))
        return BookBudgetConfig(max_sheets=int(max_sheets_raw), max_total_cells=int(max_total_cells_raw))

    max_sheets = int(budget.max_sheets)
    max_total_cells = int(budget.max_total_cells)
    if max_sheets_raw is not None:
        max_sheets = int(max_sheets_raw)
    if max_total_cells_raw is not None:
        max_total_cells = int(max_total_cells_raw)
    return BookBudgetConfig(max_sheets=int(max_sheets), max_total_cells=int(max_total_cells))


def _apply_book_export_xlsx_patch(
    export_xlsx: Optional[BookExportXlsxConfig],
    raw: Dict[str, Any],
    *,
    path: str,
) -> BookExportXlsxConfig:
    path_raw = raw.get("path")
    allow_formulas_raw = raw.get("allow_formulas")
    if "write_lock" in raw:
        msg = (
            "{}.export_xlsx.write_lock was removed; migrate to versioned outputs and locate results via <root>/manifest/latest.json".format(
                path
            )
        )
        raise ScalimWorkflowConfigError(msg, path="{}.export_xlsx.write_lock".format(path))

    if export_xlsx is None:
        if path_raw is None:
            msg = "{}.export_xlsx.path is required when creating export_xlsx".format(path)
            raise ScalimWorkflowConfigError(msg, path="{}.export_xlsx.path".format(path))
        return BookExportXlsxConfig(
            path=path_raw, allow_formulas=bool(allow_formulas_raw) if isinstance(allow_formulas_raw, bool) else False
        )

    next_path = export_xlsx.path if path_raw is None else path_raw
    next_allow_formulas = export_xlsx.allow_formulas if allow_formulas_raw is None else bool(allow_formulas_raw)
    return BookExportXlsxConfig(path=next_path, allow_formulas=bool(next_allow_formulas))


def _apply_optional_book_budget_patch(budget: Optional[BookBudgetConfig], value: object, *, path: str) -> Optional[BookBudgetConfig]:
    raw = _patch_as_opt_mapping(value, path="{}.budget".format(path))
    if raw is None:
        return None
    return _apply_book_budget_patch(budget, raw, path=path)


def _apply_optional_book_export_xlsx_patch(
    export_xlsx: Optional[BookExportXlsxConfig],
    value: object,
    *,
    path: str,
) -> Optional[BookExportXlsxConfig]:
    raw = _patch_as_opt_mapping(value, path="{}.export_xlsx".format(path))
    if raw is None:
        return None
    return _apply_book_export_xlsx_patch(export_xlsx, raw, path=path)


def _apply_optional_book_write_defaults_patch(
    *,
    kind: str,
    book_path: Any,
    budget: Optional[BookBudgetConfig],
    export_xlsx: Optional[BookExportXlsxConfig],
    allow_formulas: bool,
    write_defaults: Optional[BookWriteDefaultsConfig],
    value: object,
    path: str,
) -> Optional[BookWriteDefaultsConfig]:
    raw = _patch_as_opt_mapping(value, path="{}.write_defaults".format(path))
    if raw is None:
        return None
    return _apply_book_write_defaults_patch(
        kind=str(kind),
        book_path=book_path,
        budget=budget,
        export_xlsx=export_xlsx,
        allow_formulas=bool(allow_formulas),
        write_defaults=write_defaults,
        raw=raw,
        path=path,
    )


def _apply_book_write_defaults_patch(
    *,
    kind: str,
    book_path: Any,
    budget: Optional[BookBudgetConfig],
    export_xlsx: Optional[BookExportXlsxConfig],
    allow_formulas: bool,
    write_defaults: Optional[BookWriteDefaultsConfig],
    raw: Dict[str, Any],
    path: str,
) -> BookWriteDefaultsConfig:
    base_defaults = _effective_write_defaults(
        BookConfig(
            kind=str(kind),
            path=book_path,
            budget=budget,
            export_xlsx=export_xlsx,
            allow_formulas=bool(allow_formulas),
            write_defaults=write_defaults,
        )
    )
    return _overlay_book_write_defaults_patch(base_defaults, raw, path="{}.write_defaults".format(path))


def _validate_book_kind_semantic_contracts(
    *,
    kind: str,
    book_path: Any,
    budget: Optional[BookBudgetConfig],
    export_xlsx: Optional[BookExportXlsxConfig],
    allow_formulas: bool,
    path: str,
) -> None:
    msg: str

    # 校验 `kind` 分支约束(与 `YAML` 解析器语义保持一致).
    if kind == "xlsx_file":
        if not book_path or (isinstance(book_path, str) and not str(book_path).strip()):
            msg = "{}.path is required for kind=xlsx_file".format(path)
            raise ScalimWorkflowConfigError(msg, path="{}.path".format(path))
        if budget is not None:
            msg = "{}.budget is not allowed for kind=xlsx_file".format(path)
            raise ScalimWorkflowConfigError(msg, path="{}.budget".format(path))
        if export_xlsx is not None:
            msg = "{}.export_xlsx is not allowed for kind=xlsx_file".format(path)
            raise ScalimWorkflowConfigError(msg, path="{}.export_xlsx".format(path))
        return

    if kind == "xlsx_memory":
        if budget is None:
            msg = "{}.budget is required for kind=xlsx_memory".format(path)
            raise ScalimWorkflowConfigError(msg, path="{}.budget".format(path))
        if book_path is not None:
            msg = "{}.path is not allowed for kind=xlsx_memory".format(path)
            raise ScalimWorkflowConfigError(msg, path="{}.path".format(path))
        if allow_formulas:
            msg = "{}.allow_formulas is not allowed for kind=xlsx_memory".format(path)
            raise ScalimWorkflowConfigError(msg, path="{}.allow_formulas".format(path))
        return

    msg = "{}.kind={!r} is invalid; expected one of: xlsx_file, xlsx_memory".format(path, kind)
    raise ScalimWorkflowConfigError(msg, path="{}.kind".format(path))


def _apply_book_patch(
    base: Optional[BookConfig],
    patch: Mapping[str, object],
    *,
    path: str,
) -> BookConfig:
    kind = str(base.kind or "").strip() if base is not None else ""
    book_path: Any = base.path if base is not None else None
    budget = base.budget if base is not None else None
    export_xlsx = base.export_xlsx if base is not None else None
    allow_formulas = bool(base.allow_formulas) if base is not None else False
    write_defaults = base.write_defaults if base is not None else None

    allowed_keys = {"kind", "path", "budget", "export_xlsx", "allow_formulas", "write_defaults"}
    _patch_assert_no_unknown_keys(patch, allowed_keys=allowed_keys, path=path)

    if "kind" in patch:
        kind = _patch_as_required_non_empty_str(patch.get("kind"), path="{}.kind".format(path))

    if "path" in patch:
        book_path = patch.get("path")

    if "allow_formulas" in patch:
        allow_formulas = _patch_as_bool(patch.get("allow_formulas"), path="{}.allow_formulas".format(path))

    if "budget" in patch:
        budget = _apply_optional_book_budget_patch(budget, patch.get("budget"), path=path)

    if "export_xlsx" in patch:
        export_xlsx = _apply_optional_book_export_xlsx_patch(export_xlsx, patch.get("export_xlsx"), path=path)

    if "write_defaults" in patch:
        write_defaults = _apply_optional_book_write_defaults_patch(
            kind=str(kind),
            book_path=book_path,
            budget=budget,
            export_xlsx=export_xlsx,
            allow_formulas=bool(allow_formulas),
            write_defaults=write_defaults,
            value=patch.get("write_defaults"),
            path=path,
        )

    _validate_book_kind_semantic_contracts(
        kind=str(kind),
        book_path=book_path,
        budget=budget,
        export_xlsx=export_xlsx,
        allow_formulas=bool(allow_formulas),
        path=path,
    )

    return BookConfig(
        kind=str(kind),
        path=book_path,
        budget=budget,
        export_xlsx=export_xlsx,
        allow_formulas=bool(allow_formulas),
        write_defaults=write_defaults,
    )


def _apply_file_patch_encoding(encoding: str, patch: Mapping[str, object], *, path: str) -> str:
    if "encoding" not in patch:
        return str(encoding or DEFAULT_OUTPUT_ENCODING)
    raw_encoding = patch.get("encoding")
    if raw_encoding is None:
        return DEFAULT_OUTPUT_ENCODING
    if not isinstance(raw_encoding, str):
        msg = "{}.encoding must be a string".format(path)
        raise ScalimWorkflowConfigError(msg, path="{}.encoding".format(path))
    return str(raw_encoding).strip() or DEFAULT_OUTPUT_ENCODING


def _apply_file_patch(base: Optional[FileConfig], patch: Mapping[str, object], *, path: str) -> FileConfig:
    allowed_keys = {"kind", "path", "encoding"}
    unknown = sorted({str(k) for k in patch} - allowed_keys)
    if unknown:
        msg = "{} contains unknown keys: {}".format(path, ", ".join(unknown))
        raise ScalimWorkflowConfigError(msg, path=path)

    kind = str(base.kind or "").strip() if base is not None else ""
    file_path: Any = base.path if base is not None else None
    encoding = str(base.encoding or DEFAULT_OUTPUT_ENCODING) if base is not None else DEFAULT_OUTPUT_ENCODING

    raw_kind = patch.get("kind", kind)
    kind = str(raw_kind or "").strip() if isinstance(raw_kind, str) else ""
    if not kind:
        msg = "{}.kind must be a non-empty string".format(path)
        raise ScalimWorkflowConfigError(msg, path="{}.kind".format(path))
    if kind not in FILE_KINDS:
        msg = "{}.kind={!r} is invalid; expected one of: {}".format(path, kind, ", ".join(FILE_KINDS))
        raise ScalimWorkflowConfigError(msg, path="{}.kind".format(path))

    file_path = patch.get("path", file_path)
    if file_path is None:
        msg = "{}.path is required for kind=csv_file".format(path)
        raise ScalimWorkflowConfigError(msg, path="{}.path".format(path))

    encoding = _apply_file_patch_encoding(str(encoding), patch, path=path)
    return FileConfig(kind=str(kind), path=file_path, encoding=str(encoding))


def _book_export_path_and_options(
    book: BookConfig,
    *,
    book_id: str,
    base_dir: str,
    init_vars: Optional[Dict[str, object]],
    path_prefix: str,
) -> Tuple[str, Dict[str, object]]:
    kind = str(book.kind or "").strip()
    if kind == "xlsx_file":
        output_root = resolve_yaml_relative_output_path(
            book.path,
            base_dir=str(base_dir),
            init_vars=init_vars,
            path="{}.path".format(path_prefix),
        )
        if Path(str(output_root)).suffix.lower() == ".xlsx":
            msg = (
                "{}.path now expects an output root directory, not a file path. "
                "Migration: set path to './out' and locate outputs via <root>/manifest/latest.json."
            ).format(path_prefix)
            raise ValueError(msg)
        options: Dict[str, object] = {
            "kind": "xlsx_file",
            "allow_formulas": bool(book.allow_formulas),
        }
        return str(output_root), options

    if kind == "xlsx_memory":
        budget = book.budget
        if budget is None:
            msg = "books.kind=xlsx_memory requires budget (book_id={!r})".format(str(book_id))
            path_ref = "{}.budget".format(path_prefix)
            err = "{} (path={})".format(msg, path_ref)
            raise ValueError(err)

        export_cfg = book.export_xlsx
        output_root = ""
        export_options = None
        if export_cfg is not None:
            output_root = resolve_yaml_relative_output_path(
                export_cfg.path,
                base_dir=str(base_dir),
                init_vars=init_vars,
                path="{}.export_xlsx.path".format(path_prefix),
            )
            if Path(str(output_root)).suffix.lower() == ".xlsx":
                msg = (
                    "{}.export_xlsx.path now expects an output root directory, not a file path. "
                    "Migration: set path to './out' and locate outputs via <root>/manifest/latest.json."
                ).format(path_prefix)
                raise ValueError(msg)
            export_options = {
                "allow_formulas": bool(export_cfg.allow_formulas),
            }

        options = {
            "kind": "xlsx_memory",
            "budget": {"max_sheets": int(budget.max_sheets), "max_total_cells": int(budget.max_total_cells)},
        }
        if export_options is not None:
            options["export_xlsx"] = export_options
        return str(output_root), options

    msg = "Unknown book kind {!r} for book_id={!r}".format(kind, str(book_id))
    path_ref = "{}.kind".format(path_prefix)
    err = "{} (path={})".format(msg, path_ref)
    raise ValueError(err)


def _file_export_path_and_options(
    file_cfg: FileConfig,
    *,
    file_id: str,
    base_dir: str,
    init_vars: Optional[Dict[str, object]],
    path_prefix: str,
) -> Tuple[str, Dict[str, object]]:
    kind = str(file_cfg.kind or "").strip()
    if kind != "csv_file":
        msg = "Unknown file kind {!r} for file_id={!r}".format(kind, str(file_id))
        path_ref = "{}.kind".format(path_prefix)
        err = "{} (path={})".format(msg, path_ref)
        raise ValueError(err)

    output_root = resolve_yaml_relative_output_path(
        file_cfg.path,
        base_dir=str(base_dir),
        init_vars=init_vars,
        path="{}.path".format(path_prefix),
    )
    if Path(str(output_root)).suffix.lower() == ".csv":
        msg = (
            "{}.path now expects an output root directory, not a file path. "
            "Migration: set path to './out' and locate outputs via <root>/manifest/latest.json."
        ).format(path_prefix)
        raise ValueError(msg)
    return str(output_root), {
        "kind": "csv_file",
        "encoding": str(file_cfg.encoding or DEFAULT_OUTPUT_ENCODING),
    }


def _book_override_to_patch(override: BookResourceOverride) -> Dict[str, object]:  # noqa: C901, PLR0912
    patch: Dict[str, object] = {}
    if override.kind is not None:
        patch["kind"] = override.kind
    if override.path is not None:
        patch["path"] = override.path
    if override.allow_formulas is not None:
        patch["allow_formulas"] = override.allow_formulas
    if override.budget is not None:
        budget_patch: Dict[str, object] = {}
        if override.budget.max_sheets is not None:
            budget_patch["max_sheets"] = override.budget.max_sheets
        if override.budget.max_total_cells is not None:
            budget_patch["max_total_cells"] = override.budget.max_total_cells
        patch["budget"] = budget_patch
    if override.export_xlsx is not None:
        export_patch: Dict[str, object] = {}
        if override.export_xlsx.path is not None:
            export_patch["path"] = override.export_xlsx.path
        if override.export_xlsx.allow_formulas is not None:
            export_patch["allow_formulas"] = override.export_xlsx.allow_formulas
        patch["export_xlsx"] = export_patch
    if override.write_defaults is not None:
        defaults_patch: Dict[str, object] = {}
        if override.write_defaults.mode is not None:
            defaults_patch["mode"] = override.write_defaults.mode
        if override.write_defaults.align_by is not None:
            defaults_patch["align_by"] = override.write_defaults.align_by
        if override.write_defaults.header_policy is not None:
            defaults_patch["header_policy"] = override.write_defaults.header_policy
        if override.write_defaults.on_mismatch is not None:
            defaults_patch["on_mismatch"] = override.write_defaults.on_mismatch
        if override.write_defaults.on_conflict is not None:
            defaults_patch["on_conflict"] = override.write_defaults.on_conflict
        patch["write_defaults"] = defaults_patch
    return patch


def _file_override_to_patch(override: FileResourceOverride) -> Dict[str, object]:
    patch: Dict[str, object] = {}
    if override.kind is not None:
        patch["kind"] = override.kind
    if override.path is not None:
        patch["path"] = override.path
    if override.encoding is not None:
        patch["encoding"] = override.encoding
    return patch


def _compile_workflow_resources(  # noqa: C901, PLR0912, PLR0915
    wf_obj: WorkflowConfig,
    *,
    workflow_base_dir: Path,
    demand_cfg_by_run_id: Mapping[str, DemandConfig],
    demand_yaml_paths_by_run_id: Mapping[str, str],
    init_vars: Optional[Dict[str, object]],
    overrides_resources: Optional[ResourcesOverride],
) -> Tuple[List[WorkflowResourceIr], Dict[str, BookConfig], Dict[str, FileConfig]]:
    """编译工作流的有效 `books` 资源并返回:

    - 资源列表(`IR`)
    - 有效 `BookConfig` 映射(`book_id` -> 配置)
    - 有效 `FileConfig` 映射(`file_id` -> 配置)
    """

    msg: str

    workflow_books: Dict[str, BookConfig] = dict(wf_obj.resources.books or {})
    workflow_files: Dict[str, FileConfig] = dict(wf_obj.resources.files or {})
    demand_books: Dict[str, BookConfig] = {}
    demand_files: Dict[str, FileConfig] = {}
    demand_base_dir_by_book_id: Dict[str, str] = {}
    demand_base_dir_by_file_id: Dict[str, str] = {}

    # 1) 收集需求侧声明的 `books`(用于与 `standalone` 行为对齐).
    for run in wf_obj.runs:
        run_id = str(run.id)
        cfg = demand_cfg_by_run_id.get(run_id)
        if cfg is None:
            continue
        res = cfg.resources
        books = res.books if res is not None else {}
        files = res.files if res is not None else {}
        if not books:
            pass
        base_dir = str(_demand_base_dir(demand_yaml_paths_by_run_id.get(run_id, "")))

        for book_id, book in books.items():
            bid = str(book_id)
            if bid in workflow_books:
                # 工作流声明同名 `book_id` 时,要求与需求侧的 `kind` 兼容.
                wf_kind = str(workflow_books[bid].kind or "").strip()
                demand_kind = str(book.kind or "").strip()
                if wf_kind and demand_kind and wf_kind != demand_kind:
                    msg = "Book kind mismatch between workflow and demand (book_id={!r}, workflow_kind={!r}, demand_kind={!r})".format(
                        bid, wf_kind, demand_kind
                    )
                    raise ScalimWorkflowConfigError(msg, path="workflow.resources.books.{}".format(bid))
                continue

            existing = demand_books.get(bid)
            if existing is None:
                demand_books[bid] = book
                demand_base_dir_by_book_id[bid] = base_dir
                continue

            # 多个需求声明同一 `book_id` 时,在路径解析后要求配置等价.
            if existing != book:
                msg = "Conflicting demand book definitions for book_id={!r}; declare workflow.resources.books.{} to override".format(
                    bid, bid
                )
                raise ScalimWorkflowConfigError(msg, path="workflow.resources.books")

            # 配置相同但相对路径可能在不同 `YAML` 目录下解析出不同结果:
            # - 使用第一个 `base_dir` 作为基准
            # - 尽量确保其它需求解析得到的绝对路径一致
            # - 若需要跨目录共享,应在工作流级声明该 `book`
            first_dir = demand_base_dir_by_book_id.get(bid, base_dir)
            first_abs_path = _try_resolve_book_export_abs_path(
                existing,
                book_id=bid,
                base_dir=str(first_dir),
                init_vars=init_vars,
                path_prefix="resources.books.{}".format(bid),
            )
            current_abs_path = _try_resolve_book_export_abs_path(
                book,
                book_id=bid,
                base_dir=str(base_dir),
                init_vars=init_vars,
                path_prefix="resources.books.{}".format(bid),
            )
            if first_abs_path and current_abs_path and str(first_abs_path) != str(current_abs_path):
                msg = (
                    "Conflicting demand book paths for shared book_id={!r} across different YAML dirs; "
                    "declare workflow.resources.books.{} to unify"
                ).format(bid, bid)
                raise ScalimWorkflowConfigError(msg, path="workflow.resources.books")

        for file_id, file_cfg in files.items():
            fid = str(file_id)
            if fid in workflow_files:
                wf_kind = str(workflow_files[fid].kind or "").strip()
                demand_kind = str(file_cfg.kind or "").strip()
                if wf_kind and demand_kind and wf_kind != demand_kind:
                    msg = "File kind mismatch between workflow and demand (file_id={!r}, workflow_kind={!r}, demand_kind={!r})".format(
                        fid, wf_kind, demand_kind
                    )
                    raise ScalimWorkflowConfigError(msg, path="workflow.resources.files.{}".format(fid))
                continue
            existing_file = demand_files.get(fid)
            if existing_file is None:
                demand_files[fid] = file_cfg
                demand_base_dir_by_file_id[fid] = base_dir
                continue
            if existing_file != file_cfg:
                msg = "Conflicting demand file definitions for file_id={!r}; declare workflow.resources.files.{} to override".format(
                    fid, fid
                )
                raise ScalimWorkflowConfigError(msg, path="workflow.resources.files")

    # 2) 计算有效配置,优先级: 需求 < 工作流 < `overrides`.
    effective_books: Dict[str, BookConfig] = {}
    effective_files: Dict[str, FileConfig] = {}
    base_dir_by_book_id: Dict[str, str] = {}
    base_dir_by_file_id: Dict[str, str] = {}
    path_prefix_by_book_id: Dict[str, str] = {}
    path_prefix_by_file_id: Dict[str, str] = {}

    all_book_ids: Set[str] = set()
    all_book_ids.update(demand_books)
    all_book_ids.update(workflow_books)
    all_file_ids: Set[str] = set()
    all_file_ids.update(demand_files)
    all_file_ids.update(workflow_files)

    overrides_books_raw = None if overrides_resources is None else overrides_resources.books
    overrides_files_raw = None if overrides_resources is None else overrides_resources.files
    if overrides_books_raw:
        all_book_ids.update(str(k) for k in overrides_books_raw)
    if overrides_files_raw:
        all_file_ids.update(str(k) for k in overrides_files_raw)

    for book_id in sorted(all_book_ids):
        bid = str(book_id)
        book = None
        base_dir = None
        path_prefix = ""

        if bid in workflow_books:
            book = workflow_books[bid]
            base_dir = str(workflow_base_dir)
            path_prefix = "workflow.resources.books.{}".format(bid)
        elif bid in demand_books:
            book = demand_books[bid]
            base_dir = str(demand_base_dir_by_book_id.get(bid, workflow_base_dir))
            path_prefix = "resources.books.{}".format(bid)

        # 应用仅 `IO` 的 `overrides.resources.books.<id>` 补丁覆盖(按 `deep-merge` 语义).
        if overrides_books_raw is not None and bid in overrides_books_raw:
            book_override = overrides_books_raw[bid]
            if not isinstance(book_override, BookResourceOverride):
                msg = "overrides.resources.books.{} must be a BookResourceOverride".format(bid)
                raise ScalimWorkflowConfigError(msg, path="overrides.resources.books.{}".format(bid))
            patch = _book_override_to_patch(book_override)
            if book is None:
                book = BookConfig(kind="")
                base_dir = str(workflow_base_dir)
            book = _apply_book_patch(book, patch, path="overrides.resources.books.{}".format(bid))
            path_prefix = "overrides.resources.books.{}".format(bid)

        if book is None or base_dir is None:
            continue
        effective_books[bid] = book
        base_dir_by_book_id[bid] = base_dir
        path_prefix_by_book_id[bid] = path_prefix

    for file_id in sorted(all_file_ids):
        fid = str(file_id)
        file_cfg = None
        base_dir = None
        path_prefix = ""

        if fid in workflow_files:
            file_cfg = workflow_files[fid]
            base_dir = str(workflow_base_dir)
            path_prefix = "workflow.resources.files.{}".format(fid)
        elif fid in demand_files:
            file_cfg = demand_files[fid]
            base_dir = str(demand_base_dir_by_file_id.get(fid, workflow_base_dir))
            path_prefix = "resources.files.{}".format(fid)

        if overrides_files_raw is not None and fid in overrides_files_raw:
            file_override = overrides_files_raw[fid]
            if not isinstance(file_override, FileResourceOverride):
                msg = "overrides.resources.files.{} must be a FileResourceOverride".format(fid)
                raise ScalimWorkflowConfigError(msg, path="overrides.resources.files.{}".format(fid))
            patch = _file_override_to_patch(file_override)
            if file_cfg is None:
                file_cfg = FileConfig(kind="")
                base_dir = str(workflow_base_dir)
            file_cfg = _apply_file_patch(file_cfg, patch, path="overrides.resources.files.{}".format(fid))
            path_prefix = "overrides.resources.files.{}".format(fid)

        if file_cfg is None or base_dir is None:
            continue  # pragma: no cover  # pragma: allow-no-cover unreachable: all_file_ids derived from workflow/demand/overrides
        effective_files[fid] = file_cfg
        base_dir_by_file_id[fid] = base_dir
        path_prefix_by_file_id[fid] = path_prefix

    resources: List[WorkflowResourceIr] = []
    for bid, book in sorted(effective_books.items(), key=lambda kv: str(kv[0])):
        base_dir = base_dir_by_book_id.get(str(bid), str(workflow_base_dir))
        prefix = path_prefix_by_book_id.get(str(bid)) or (
            "workflow.resources.books.{}".format(str(bid)) if str(bid) in workflow_books else "resources.books.{}".format(str(bid))
        )
        try:
            export_path, options = _book_export_path_and_options(
                book,
                book_id=str(bid),
                base_dir=str(base_dir),
                init_vars=init_vars,
                path_prefix=prefix,
            )
        except (TypeError, ValueError) as exc:
            raise ScalimWorkflowConfigError(str(exc), path=prefix) from exc

        resources.append(
            WorkflowResourceIr(
                resource_id=str(bid),
                resource_type="book",
                path=str(export_path or ""),
                options=options,
            )
        )

    for fid, file_cfg in sorted(effective_files.items(), key=lambda kv: str(kv[0])):
        base_dir = base_dir_by_file_id.get(str(fid), str(workflow_base_dir))
        prefix = path_prefix_by_file_id.get(str(fid)) or (
            "workflow.resources.files.{}".format(str(fid)) if str(fid) in workflow_files else "resources.files.{}".format(str(fid))
        )
        try:
            export_path, options = _file_export_path_and_options(
                file_cfg,
                file_id=str(fid),
                base_dir=str(base_dir),
                init_vars=init_vars,
                path_prefix=prefix,
            )
        except (TypeError, ValueError) as exc:
            raise ScalimWorkflowConfigError(str(exc), path=prefix) from exc

        resources.append(
            WorkflowResourceIr(
                resource_id=str(fid),
                resource_type="csv",
                path=str(export_path or ""),
                options=options,
            )
        )

    return resources, effective_books, effective_files


def _build_demand_nodes_and_graph(
    wf_obj: WorkflowConfig,
    *,
    workflow_yaml_path: str,
    path_aliases: Optional[Mapping[str, str]],
    allowed_yaml_roots: Optional[Tuple[str, ...]],
) -> Tuple[
    List[WorkflowAnyNodeIr],
    List[WorkflowEdgeIr],
    Dict[str, Tuple[str, ...]],
    Dict[str, str],
    Dict[str, List[str]],
    Dict[str, int],
]:
    nodes: List[WorkflowAnyNodeIr] = []
    edges: List[WorkflowEdgeIr] = []
    slots_by_node_id: Dict[str, Tuple[str, ...]] = {}
    demand_yaml_paths_by_run_id: Dict[str, str] = {}
    direct_dependents_by_run_id: Dict[str, List[str]] = {}
    demand_node_pos_by_run_id: Dict[str, int] = {}

    for idx, run in enumerate(wf_obj.runs):
        demand_path = resolve_workflow_demand_path(
            run.demand,
            workflow_yaml_path=workflow_yaml_path,
            path_aliases=path_aliases,
            run_id=run.id,
            allowed_yaml_roots=allowed_yaml_roots,
        )
        node_id = str(run.id)
        run_deps = tuple(str(d) for d in (run.depends_on or ()))
        main_rows_from_run_id = run.main_rows_from_run_id
        if main_rows_from_run_id is not None:
            main_rows_from_run_id = str(main_rows_from_run_id or "").strip() or None
        init_vars = run.init_vars
        if init_vars is not None:
            init_vars = dict(init_vars)
        demand_yaml_paths_by_run_id[node_id] = str(demand_path)
        nodes.append(
            WorkflowNodeIr(
                node_id=node_id,
                node_type=WorkflowNodeType.DEMAND,
                decl_order=int(idx),
                deps=run_deps,
                demand_path=str(demand_path),
                init_vars=init_vars,
                main_rows_from_run_id=main_rows_from_run_id,
            )
        )
        demand_node_pos_by_run_id[node_id] = int(len(nodes) - 1)
        for dep_id in run_deps:
            edges.append(WorkflowEdgeIr(from_node_id=str(dep_id), to_node_id=node_id))
            direct_dependents_by_run_id.setdefault(str(dep_id), []).append(node_id)
        slots_by_node_id[node_id] = ("output_path", "outputs")

    return (
        nodes,
        edges,
        slots_by_node_id,
        demand_yaml_paths_by_run_id,
        direct_dependents_by_run_id,
        demand_node_pos_by_run_id,
    )


def _load_demands(
    demand_yaml_paths_by_run_id: Mapping[str, str],
    *,
    template_vars: Optional[Mapping[str, object]],
    template_sandbox: str,
    rendered_yaml_max_len: int,
    allowed_yaml_roots: Optional[Tuple[str, ...]],
) -> Dict[str, DemandConfig]:
    loader = YamlDemandLoader()
    demand_cfg_by_run_id: Dict[str, DemandConfig] = {}
    for node_id, yaml_path in demand_yaml_paths_by_run_id.items():
        try:
            cfg = loader.load(
                str(yaml_path),
                template_vars=template_vars,
                template_sandbox=template_sandbox,
                rendered_yaml_max_len=rendered_yaml_max_len,
                allowed_yaml_roots=allowed_yaml_roots,
            )
        except Exception as exc:
            msg = "Failed to load demand YAML for workflow compile: run_id={!r}, demand_path={!r}: {}".format(
                str(node_id),
                str(yaml_path),
                exc,
            )
            raise ScalimWorkflowConfigError(msg, path="workflow.runs[*].demand") from exc
        demand_cfg_by_run_id[str(node_id)] = cfg
    return demand_cfg_by_run_id


def _parse_output_extra_sheet_override(
    raw: object,
    *,
    path: str,
) -> Optional[OutputExtraSheetConfig]:
    if raw is None:
        return None
    if isinstance(raw, bool):
        if not raw:
            return None
        return OutputExtraSheetConfig()
    if not isinstance(raw, OutputExtraSheetOverride):
        msg = "{} must be a boolean or an OutputExtraSheetOverride".format(path)
        raise ScalimWorkflowConfigError(msg, path=str(path))

    sheet = str(raw.sheet).strip() if raw.sheet is not None else None

    raw_path = raw.path
    if raw_path is not None and not isinstance(raw_path, (str, os.PathLike)):
        msg = "{}.path must be a string or PathLike".format(path)
        raise ScalimWorkflowConfigError(msg, path="{}.path".format(path))
    resolved_path = str(raw_path) if raw_path is not None else None

    allow_formulas = raw.allow_formulas
    if allow_formulas is not None and not isinstance(allow_formulas, bool):
        msg = "{}.allow_formulas must be a bool".format(path)
        raise ScalimWorkflowConfigError(msg, path="{}.allow_formulas".format(path))

    return OutputExtraSheetConfig(
        path=resolved_path,
        sheet=sheet,
        allow_formulas=allow_formulas,
    )


def _apply_overrides_output_extras(
    demand_cfg_by_run_id: Dict[str, DemandConfig], *, overrides: Optional[RunOverrides]
) -> Dict[str, DemandConfig]:
    if overrides is None or overrides.output_extras is None:
        return demand_cfg_by_run_id
    extras = overrides.output_extras
    if not isinstance(extras, OutputExtrasOverride):
        msg = "overrides.output_extras must be an OutputExtrasOverride"
        raise ScalimWorkflowConfigError(msg, path="overrides.output_extras")

    meta = _parse_output_extra_sheet_override(extras.meta, path="overrides.output_extras.meta")
    audit = _parse_output_extra_sheet_override(extras.audit, path="overrides.output_extras.audit")

    next_cfg: Dict[str, DemandConfig] = {}
    for run_id, cfg in demand_cfg_by_run_id.items():
        next_cfg[str(run_id)] = replace(cfg, meta=meta, audit=audit)
    return next_cfg


def _parse_overrides_outputs_defaults_book_id(defaults: Optional[OutputsDefaultsOverride]) -> Optional[str]:
    if defaults is None:
        return None
    book_id = str(defaults.to.book or "").strip()
    if not book_id:
        msg = "overrides.outputs_defaults.to.book is required"
        raise ScalimWorkflowConfigError(msg, path="overrides.outputs_defaults.to.book")
    return book_id


def _apply_default_book_binding_to_outputs(
    outputs: Tuple[OutputTargetConfig, ...],
    *,
    default_book_id: str,
) -> Tuple[OutputTargetConfig, ...]:
    if not outputs or not default_book_id:
        return outputs

    updated: List[OutputTargetConfig] = []
    for out_cfg in outputs:
        to_cfg = out_cfg.to
        if to_cfg is None:
            updated.append(replace(out_cfg, to=OutputToConfig(book=str(default_book_id))))
            continue

        file_id = str(to_cfg.file or "").strip() if to_cfg.file is not None else ""
        book_id = str(to_cfg.book or "").strip() if to_cfg.book is not None else ""
        if file_id or book_id:
            updated.append(out_cfg)
            continue

        updated.append(replace(out_cfg, to=replace(to_cfg, book=str(default_book_id))))

    return tuple(updated)


def _effective_outputs_for_workflow_compile(  # noqa: C901
    config: DemandConfig,
    *,
    overrides_outputs: Optional[Sequence[OutputOverride]],
    default_book_id: Optional[str],
) -> Tuple[OutputTargetConfig, ...]:
    if overrides_outputs is None:
        yaml_outputs = tuple(config.outputs or ())
        if default_book_id is not None:
            yaml_outputs = _apply_default_book_binding_to_outputs(yaml_outputs, default_book_id=str(default_book_id))
        return yaml_outputs

    # 最小解析器: 仅抽取 `name`/`to`/`write`;完整校验在需求编译阶段完成.
    outputs: List[OutputTargetConfig] = []
    for idx, raw in enumerate(overrides_outputs):
        if not isinstance(raw, OutputOverride):
            msg = "overrides.outputs.{} must be an OutputOverride".format(int(idx))
            raise ScalimWorkflowConfigError(msg, path="overrides.outputs")

        name = str(raw.name or "").strip()
        if not name:
            msg = "overrides.outputs.{}.name is required".format(int(idx))
            raise ScalimWorkflowConfigError(msg, path="overrides.outputs")

        to_override = raw.to
        if not isinstance(to_override, OutputToOverride):
            msg = "overrides.outputs.{}.to must be an OutputToOverride".format(int(idx))
            raise ScalimWorkflowConfigError(msg, path="overrides.outputs.{}.to".format(int(idx)))
        file_id = str(to_override.file or "").strip() if to_override.file is not None else ""
        book_id = str(to_override.book or "").strip() if to_override.book is not None else ""
        sheet = str(to_override.sheet or "").strip() if to_override.sheet is not None else ""

        if file_id and (book_id or sheet):
            msg = "overrides.outputs.{}.to declares to.file and to.book/to.sheet; declare only one destination".format(int(idx))
            raise ScalimWorkflowConfigError(msg, path="overrides.outputs.{}.to".format(int(idx)))

        if not file_id:
            book_id = book_id or str(default_book_id or "").strip()
            if not book_id:
                msg = (
                    "Missing outputs to.book binding for output {!r}; set overrides.outputs.{}.to.book explicitly "
                    "or provide overrides.outputs_defaults.to.book"
                ).format(str(name), int(idx))
                raise ScalimWorkflowConfigError(msg, path="overrides.outputs.{}.to.book".format(int(idx)))

        to_cfg = OutputToConfig(
            file=str(file_id).strip() or None,
            book=str(book_id).strip() or None,
            sheet=str(sheet).strip() or None,
        )

        write_obj = raw.write
        write_cfg = None
        if write_obj is not None:
            if not isinstance(write_obj, OutputWriteOverride):
                msg = "overrides.outputs.{}.write must be an OutputWriteOverride".format(int(idx))
                raise ScalimWorkflowConfigError(msg, path="overrides.outputs.{}.write".format(int(idx)))

            write_raw = cast("Any", write_obj)  # pragma: allow-cast typed override field access boundary
            write_cfg = OutputWriteConfig(
                include_header=write_raw.include_header,
                header_fields_output_by=write_raw.header_fields_output_by,
            )

        outputs.append(
            OutputTargetConfig(
                name=str(name),
                to=to_cfg,
                write=write_cfg,
                fields=None,
            )
        )
    return tuple(outputs)


def _build_write_node_for_book(
    *,
    node_id: str,
    decl_order: int,
    deps: Sequence[str],
    book_id: str,
    sheet_name: str,
    input_node_id: str,
    input_output_id: str,
    mode: str,
    write_defaults: object,
    write_defaults_mode_path: str,
) -> WorkflowAnyNodeIr:
    effective_defaults = cast("Any", write_defaults)  # pragma: allow-cast write defaults typed boundary

    if mode == "sheet":
        return WriteSheetNodeIr(
            node_id=str(node_id),
            node_type=WorkflowNodeType.WRITE_SHEET,
            decl_order=int(decl_order),
            deps=tuple(deps),
            resource_type="book",
            resource_id=str(book_id),
            sheet=str(sheet_name),
            input_node_id=str(input_node_id),
            input_output_id=str(input_output_id),
            on_conflict=str(effective_defaults.on_conflict or DEFAULT_BOOK_WRITE_ON_CONFLICT),
        )

    if mode == "append":
        return AppendSheetNodeIr(
            node_id=str(node_id),
            node_type=WorkflowNodeType.APPEND_SHEET,
            decl_order=int(decl_order),
            deps=tuple(deps),
            resource_type="book",
            resource_id=str(book_id),
            sheet=str(sheet_name),
            input_node_id=str(input_node_id),
            input_output_id=str(input_output_id),
            align_by=str(effective_defaults.align_by or DEFAULT_BOOK_WRITE_ALIGN_BY),
            header_policy=str(effective_defaults.header_policy or DEFAULT_BOOK_WRITE_HEADER_POLICY),
            on_mismatch=str(effective_defaults.on_mismatch or DEFAULT_BOOK_WRITE_ON_MISMATCH),
        )

    msg = "Unsupported books.write_defaults.mode={!r} (book_id={!r})".format(str(mode), str(book_id))
    raise ScalimWorkflowConfigError(msg, path=str(write_defaults_mode_path))


def _append_write_nodes_from_runs(  # noqa: C901, PLR0912, PLR0915
    wf_obj: WorkflowConfig,
    *,
    demand_cfg_by_run_id: Mapping[str, DemandConfig],
    nodes: List[WorkflowAnyNodeIr],
    edges: List[WorkflowEdgeIr],
    effective_books: Mapping[str, BookConfig],
    effective_files: Mapping[str, FileConfig],
    overrides_outputs: Optional[Sequence[OutputOverride]],
    default_book_id: Optional[str],
) -> Dict[str, List[str]]:
    last_write_node_id_by_book_id: Dict[str, str] = {}
    last_write_node_id_by_file_id: Dict[str, str] = {}
    xlsx_memory_write_node_ids_by_run_id: Dict[str, List[str]] = {}

    for run in wf_obj.runs:
        cfg = demand_cfg_by_run_id.get(str(run.id))
        if cfg is None:
            continue

        outputs = _effective_outputs_for_workflow_compile(cfg, overrides_outputs=overrides_outputs, default_book_id=default_book_id)
        if not outputs:
            continue

        outputs_path = "outputs" if overrides_outputs is None else "overrides.outputs"

        next_write_idx = 0
        for out_idx, out_cfg in enumerate(outputs):
            file_id, file_ref_path = _effective_file_binding_for_output(
                out_cfg,
                idx=int(out_idx),
                outputs_path=outputs_path,
            )
            if file_id is not None:
                if effective_files.get(str(file_id)) is None:
                    msg = (
                        "Missing file resource id {!r} referenced by {}. "
                        "Hint: declare resources.files.{} in the demand YAML, declare workflow.resources.files.{} in the workflow YAML, "
                        "or provide overrides.resources.files.{} in Python."
                    ).format(str(file_id), str(file_ref_path), str(file_id), str(file_id), str(file_id))
                    raise ScalimWorkflowConfigError(msg, path=str(file_ref_path))
                node_id = "{}write.{}.{}".format(_INTERNAL_NODE_ID_PREFIX, str(run.id), int(next_write_idx))
                next_write_idx += 1
                decl_order = len(nodes)
                write_deps = [str(run.id)]
                prev_write_id = last_write_node_id_by_file_id.get(str(file_id))
                if prev_write_id is not None:
                    write_deps.append(str(prev_write_id))
                last_write_node_id_by_file_id[str(file_id)] = str(node_id)

                nodes.append(
                    AppendSheetNodeIr(
                        node_id=str(node_id),
                        node_type=WorkflowNodeType.APPEND_SHEET,
                        decl_order=int(decl_order),
                        deps=tuple(write_deps),
                        resource_type="csv",
                        resource_id=str(file_id),
                        sheet=None,
                        input_node_id=str(run.id),
                        input_output_id=str(out_cfg.name),
                        align_by="header",
                        header_policy="once",
                        on_mismatch="error",
                    )
                )
                for dep_id in write_deps:
                    edges.append(WorkflowEdgeIr(from_node_id=str(dep_id), to_node_id=str(node_id)))
                continue

            book_id, book_ref_path = _effective_book_binding_for_output(
                out_cfg,
                idx=int(out_idx),
                outputs_path=outputs_path,
            )
            if book_id is None:
                msg = (
                    "Missing outputs to.book binding for output {!r}; set {}.{}.to.book explicitly. "
                    "Reuse the binding with YAML anchors (`_templates`) or `$import` if needed."
                ).format(str(out_cfg.name), str(outputs_path), int(out_idx))
                raise ScalimWorkflowConfigError(msg, path=str(book_ref_path))

            book = effective_books.get(str(book_id))
            if book is None:
                msg = (
                    "Missing book resource id {!r} referenced by {}. "
                    "Hint: declare resources.books.{} in the demand YAML, declare workflow.resources.books.{} in the workflow YAML, "
                    "or provide overrides.resources.books.{} in Python."
                ).format(str(book_id), str(book_ref_path), str(book_id), str(book_id), str(book_id))
                raise ScalimWorkflowConfigError(msg, path=str(book_ref_path))
            _validate_xlsx_memory_align_by(
                book=book,
                book_id=str(book_id),
            )

            sheet_name, sheet_ref_path = _effective_sheet_name_for_output(out_cfg, idx=int(out_idx), outputs_path=outputs_path)
            try:
                _validate_excel_sheet_name(sheet_name, path=str(sheet_ref_path))
            except ValueError as exc:
                raise ScalimWorkflowConfigError(str(exc), path=str(sheet_ref_path)) from exc

            base_defaults = _effective_write_defaults(book)
            effective_defaults = base_defaults
            mode = str(effective_defaults.mode or DEFAULT_BOOK_WRITE_MODE)

            node_id = "{}write.{}.{}".format(_INTERNAL_NODE_ID_PREFIX, str(run.id), int(next_write_idx))
            next_write_idx += 1
            decl_order = len(nodes)
            write_deps: List[str] = [str(run.id)]

            prev_write_id = last_write_node_id_by_book_id.get(str(book_id))
            if prev_write_id is not None:
                write_deps.append(str(prev_write_id))
            last_write_node_id_by_book_id[str(book_id)] = str(node_id)

            node = _build_write_node_for_book(
                node_id=str(node_id),
                decl_order=int(decl_order),
                deps=tuple(write_deps),
                book_id=str(book_id),
                sheet_name=str(sheet_name),
                input_node_id=str(run.id),
                input_output_id=str(out_cfg.name),
                mode=str(mode),
                write_defaults=effective_defaults,
                write_defaults_mode_path="workflow.resources.books.{}.write_defaults.mode".format(str(book_id)),
            )

            nodes.append(node)
            for dep_id in write_deps:
                edges.append(WorkflowEdgeIr(from_node_id=str(dep_id), to_node_id=str(node_id)))

            kind = str(book.kind or "").strip()
            if kind == "xlsx_memory":
                xlsx_memory_write_node_ids_by_run_id.setdefault(str(run.id), []).append(str(node_id))

        # `meta`/`audit` 额外工作表: 在工作流模式下通过推导的写入节点写出.
        extras: List[Tuple[str, object, str]] = []
        if cfg.meta is not None:
            extras.append(("meta", cfg.meta, "__meta__"))
        if cfg.audit is not None:
            extras.append(("audit", cfg.audit, "__audit__"))
        if extras:
            default_book_id = None
            default_book_ref = "outputs[*].to.book"
            for scan_idx, scan_out in enumerate(outputs):
                scan_file_id, _scan_file_ref = _effective_file_binding_for_output(
                    scan_out,
                    idx=int(scan_idx),
                    outputs_path=outputs_path,
                )
                if scan_file_id is not None:
                    continue
                candidate, cand_ref = _effective_book_binding_for_output(
                    scan_out,
                    idx=int(scan_idx),
                    outputs_path=outputs_path,
                )
                # pragma: allow-no-branch unreachable: non-file outputs already validated to have a non-empty book binding
                if candidate:  # pragma: no branch
                    default_book_id, default_book_ref = candidate, cand_ref
                    break

            if default_book_id is None:
                msg = "meta/audit requires at least one Excel output with outputs[*].to.book"
                raise ScalimWorkflowConfigError(msg, path=str(default_book_ref))

            book = effective_books.get(str(default_book_id))
            if book is None:  # pragma: no cover  # pragma: allow-no-cover unreachable: first excel output binding already validated above
                msg = (
                    "Missing book resource id {!r} referenced by {}. "
                    "Hint: declare resources.books.{} in the demand YAML, declare workflow.resources.books.{} in the workflow YAML, "
                    "or provide overrides.resources.books.{} in Python."
                ).format(
                    str(default_book_id),
                    str(default_book_ref),
                    str(default_book_id),
                    str(default_book_id),
                    str(default_book_id),
                )
                raise ScalimWorkflowConfigError(msg, path=str(default_book_ref))

            base_defaults = _effective_write_defaults(book)
            effective_defaults = base_defaults
            mode = str(effective_defaults.mode or DEFAULT_BOOK_WRITE_MODE)
            _validate_xlsx_memory_align_by(
                book=book,
                book_id=str(default_book_id),
            )

            for extra_id, extra_cfg_obj, default_sheet in extras:
                extra_cfg = cast("Any", extra_cfg_obj)  # pragma: allow-cast output extra sheet cfg typed narrowing
                sheet_name = str(extra_cfg.sheet or default_sheet)
                sheet_ref_path = "{}.{}".format(extra_id, "sheet")
                try:
                    _validate_excel_sheet_name(sheet_name, path=str(sheet_ref_path))
                except ValueError as exc:
                    raise ScalimWorkflowConfigError(str(exc), path=str(sheet_ref_path)) from exc

                node_id = "{}write.{}.{}".format(_INTERNAL_NODE_ID_PREFIX, str(run.id), int(next_write_idx))
                next_write_idx += 1
                decl_order = len(nodes)
                write_deps = [str(run.id)]
                prev_write_id = last_write_node_id_by_book_id.get(str(default_book_id))
                # pragma: allow-no-branch unreachable: default book already has at least one write node before extras
                if prev_write_id is not None:  # pragma: no branch
                    write_deps.append(str(prev_write_id))
                last_write_node_id_by_book_id[str(default_book_id)] = str(node_id)

                node = _build_write_node_for_book(
                    node_id=str(node_id),
                    decl_order=int(decl_order),
                    deps=tuple(write_deps),
                    book_id=str(default_book_id),
                    sheet_name=str(sheet_name),
                    input_node_id=str(run.id),
                    input_output_id=str(extra_id),
                    mode=str(mode),
                    write_defaults=effective_defaults,
                    write_defaults_mode_path="workflow.resources.books.{}.write_defaults.mode".format(str(default_book_id)),
                )

                nodes.append(node)
                for dep_id in write_deps:
                    edges.append(WorkflowEdgeIr(from_node_id=str(dep_id), to_node_id=str(node_id)))

                kind = str(book.kind or "").strip()
                if kind == "xlsx_memory":
                    xlsx_memory_write_node_ids_by_run_id.setdefault(str(run.id), []).append(str(node_id))

    return xlsx_memory_write_node_ids_by_run_id


def _inject_xlsx_memory_write_dependencies(
    xlsx_memory_write_node_ids_by_run_id: Mapping[str, List[str]],
    direct_dependents_by_run_id: Mapping[str, List[str]],
    demand_node_pos_by_run_id: Mapping[str, int],
    nodes: List[WorkflowAnyNodeIr],
    edges: List[WorkflowEdgeIr],
) -> None:
    for producer_node_id, write_node_ids in xlsx_memory_write_node_ids_by_run_id.items():
        for consumer_node_id in direct_dependents_by_run_id.get(str(producer_node_id), []):
            pos = demand_node_pos_by_run_id.get(str(consumer_node_id))
            if pos is None:
                continue
            consumer = nodes[int(pos)]
            if not isinstance(consumer, WorkflowNodeIr):
                continue
            deps: List[str] = list(consumer.deps or ())
            for write_node_id in write_node_ids:
                if str(write_node_id) not in deps:
                    deps.append(str(write_node_id))
                    edges.append(WorkflowEdgeIr(from_node_id=str(write_node_id), to_node_id=str(consumer_node_id)))
            if deps != list(consumer.deps or ()):
                nodes[int(pos)] = replace(consumer, deps=tuple(deps))


def _build_workflow_cache_pool_ir(raw_cache_pool: Optional[WorkflowCachePoolOptions]) -> Optional[WorkflowCachePoolIr]:
    if raw_cache_pool is None:
        return None
    budget = WorkflowCachePoolBudgetIr(
        max_entries=int(raw_cache_pool.budget.max_entries),
        over_budget_policy=str(raw_cache_pool.budget.over_budget_policy),
    )
    pins = tuple(WorkflowCachePoolPinIr(kind=str(pin.kind), source_id=str(pin.source_id)) for pin in (raw_cache_pool.pin or ()))
    return WorkflowCachePoolIr(
        conflict_policy=str(raw_cache_pool.conflict_policy),
        release_policy=str(raw_cache_pool.release_policy),
        budget=budget,
        pin=pins,
    )


def _build_workflow_ctx_ir(raw_ctx: WorkflowCtxOptions) -> WorkflowCtxOptionsIr:
    return WorkflowCtxOptionsIr(
        max_value_bytes=int(raw_ctx.max_value_bytes),
        max_bytes=int(raw_ctx.max_bytes),
    )


def _parse_workflow_option_finite_number(raw: object, *, path: str, positive: bool) -> float:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        msg = "{} must be a finite {}number".format(path, "positive " if positive else "")
        raise TypeError(msg)
    value = float(raw)
    if not math.isfinite(value):
        msg = "{} must be a finite {}number".format(path, "positive " if positive else "")
        raise ValueError(msg)
    if positive and value <= 0:
        msg = "{} must be a finite positive number".format(path)
        raise ValueError(msg)
    if not positive and value < 0:
        msg = "{} must be a finite non-negative number".format(path)
        raise ValueError(msg)
    return float(value)


def _validate_workflow_resources_wait_override(raw: object) -> WorkflowResourcesWaitOptions:
    if not isinstance(raw, WorkflowResourcesWaitOptions):
        msg = "workflow_resources_wait must be a WorkflowResourcesWaitOptions"
        raise TypeError(msg)

    diagnostics = raw.diagnostics
    if not isinstance(diagnostics, WorkflowResourcesWaitDiagnosticsOptions):
        msg = "workflow_resources_wait.diagnostics must be a WorkflowResourcesWaitDiagnosticsOptions"
        raise TypeError(msg)
    if not isinstance(diagnostics.enabled, bool):
        msg = "workflow_resources_wait.diagnostics.enabled must be a bool"
        raise TypeError(msg)
    if not isinstance(diagnostics.capture_owner_callsite, bool):
        msg = "workflow_resources_wait.diagnostics.capture_owner_callsite must be a bool"
        raise TypeError(msg)

    _ = _parse_workflow_option_finite_number(raw.max_wait_s, path="workflow_resources_wait.max_wait_s", positive=True)
    _ = _parse_workflow_option_finite_number(
        diagnostics.warn_after_s,
        path="workflow_resources_wait.diagnostics.warn_after_s",
        positive=False,
    )
    if diagnostics.repeat_every_s is not None:
        _ = _parse_workflow_option_finite_number(
            diagnostics.repeat_every_s,
            path="workflow_resources_wait.diagnostics.repeat_every_s",
            positive=True,
        )
    return raw


def _build_workflow_resources_wait_ir(raw_resources_wait: WorkflowResourcesWaitOptions) -> WorkflowResourcesWaitOptionsIr:
    raw_diagnostics = raw_resources_wait.diagnostics
    return WorkflowResourcesWaitOptionsIr(
        max_wait_s=float(raw_resources_wait.max_wait_s),
        diagnostics=WorkflowResourcesWaitDiagnosticsIr(
            enabled=bool(raw_diagnostics.enabled),
            warn_after_s=float(raw_diagnostics.warn_after_s),
            repeat_every_s=float(raw_diagnostics.repeat_every_s) if raw_diagnostics.repeat_every_s is not None else None,
            capture_owner_callsite=bool(raw_diagnostics.capture_owner_callsite),
        ),
    )


def _normalize_workflow_output_staging_override(raw: object) -> WorkflowOutputStagingOptions:
    if not isinstance(raw, WorkflowOutputStagingOptions):
        msg = "workflow_output_staging must be a WorkflowOutputStagingOptions"
        raise TypeError(msg)

    dir_name = str(raw.dir_name or "").strip()
    if not dir_name:
        msg = "workflow_output_staging.dir_name must be a non-empty string"
        raise ValueError(msg)
    if dir_name in (".", "..") or "/" in dir_name or "\\" in dir_name:
        msg = "workflow_output_staging.dir_name must be a simple directory name (no separators)"
        raise ValueError(msg)
    if not isinstance(raw.keep_on_success, bool):
        msg = "workflow_output_staging.keep_on_success must be a bool"
        raise TypeError(msg)
    if not isinstance(raw.keep_on_failure, bool):
        msg = "workflow_output_staging.keep_on_failure must be a bool"
        raise TypeError(msg)

    return WorkflowOutputStagingOptions(
        dir_name=str(dir_name),
        keep_on_success=bool(raw.keep_on_success),
        keep_on_failure=bool(raw.keep_on_failure),
    )


def _build_workflow_output_staging_ir(raw_output_staging: WorkflowOutputStagingOptions) -> WorkflowOutputStagingOptionsIr:
    return WorkflowOutputStagingOptionsIr(
        dir_name=str(raw_output_staging.dir_name),
        keep_on_success=bool(raw_output_staging.keep_on_success),
        keep_on_failure=bool(raw_output_staging.keep_on_failure),
    )


def _build_workflow_options_ir(
    wf_obj: WorkflowConfig,
    *,
    workflow_resources_wait: Optional[WorkflowResourcesWaitOptions] = None,
    workflow_output_staging: Optional[WorkflowOutputStagingOptions] = None,
) -> WorkflowOptionsIr:
    cache_pool = _build_workflow_cache_pool_ir(wf_obj.options.cache_pool)
    ctx = _build_workflow_ctx_ir(wf_obj.options.ctx)

    raw_resources_wait = wf_obj.options.resources_wait if workflow_resources_wait is None else workflow_resources_wait
    raw_resources_wait = _validate_workflow_resources_wait_override(raw_resources_wait)
    resources_wait = _build_workflow_resources_wait_ir(raw_resources_wait)

    raw_output_staging = wf_obj.options.output_staging if workflow_output_staging is None else workflow_output_staging
    raw_output_staging = _normalize_workflow_output_staging_override(raw_output_staging)
    output_staging = _build_workflow_output_staging_ir(raw_output_staging)

    return WorkflowOptionsIr(
        max_concurrency=int(wf_obj.options.max_concurrency),
        failure_policy=str(wf_obj.options.failure_policy or "all_fail"),
        cache_pool=cache_pool,
        ctx=ctx,
        resources_wait=resources_wait,
        output_staging=output_staging,
    )


def compile_workflow_ir(
    wf: object,
    *,
    workflow_yaml_path: str,
    path_aliases: Optional[Mapping[str, str]],
    template_vars: Optional[Mapping[str, object]] = None,
    template_sandbox: str = "safe",
    rendered_yaml_max_len: int = DEFAULT_RENDERED_YAML_MAX_LEN,
    allowed_yaml_roots: Optional[Tuple[str, ...]] = None,
    init_vars: Optional[Dict[str, object]] = None,
    overrides: Optional[object] = None,
    workflow_resources_wait: Optional[WorkflowResourcesWaitOptions] = None,
    workflow_output_staging: Optional[WorkflowOutputStagingOptions] = None,
) -> WorkflowCompileResult:
    """将工作流配置编译为工作流 `IR`.

    说明:
    - `overrides` 为 `RunOverrides` 强类型覆盖项,用于 `resources` 覆盖、`outputs_defaults` 与 `outputs` 替换.
    """
    if overrides is not None and not isinstance(overrides, RunOverrides):
        msg = (
            "overrides must be a RunOverrides (typed dataclasses); legacy YAML-shaped overrides mappings were removed. "
            "Migrate to RunOverrides(outputs=(OutputOverride(...),), "
            "resources=ResourcesOverride(...), outputs_defaults=OutputsDefaultsOverride(...))."
        )
        raise ScalimWorkflowConfigError(msg, path="overrides")
    overrides_typed = overrides
    wf_obj = cast("WorkflowConfig", wf)  # pragma: allow-cast workflow config typed narrowing

    workflow_base_dir = _workflow_base_dir(workflow_yaml_path)

    (
        nodes,
        edges,
        slots_by_node_id,
        demand_yaml_paths_by_run_id,
        direct_dependents_by_run_id,
        demand_node_pos_by_run_id,
    ) = _build_demand_nodes_and_graph(
        wf_obj,
        workflow_yaml_path=workflow_yaml_path,
        path_aliases=path_aliases,
        allowed_yaml_roots=allowed_yaml_roots,
    )

    demand_cfg_by_run_id = _load_demands(
        demand_yaml_paths_by_run_id,
        template_vars=template_vars,
        template_sandbox=template_sandbox,
        rendered_yaml_max_len=rendered_yaml_max_len,
        allowed_yaml_roots=allowed_yaml_roots,
    )
    demand_cfg_by_run_id = _apply_overrides_output_extras(demand_cfg_by_run_id, overrides=overrides_typed)

    overrides_resources = None if overrides_typed is None else overrides_typed.resources
    overrides_outputs = None if overrides_typed is None else overrides_typed.outputs
    default_book_id = _parse_overrides_outputs_defaults_book_id(None if overrides_typed is None else overrides_typed.outputs_defaults)

    resources, effective_books, effective_files = _compile_workflow_resources(
        wf_obj,
        workflow_base_dir=workflow_base_dir,
        demand_cfg_by_run_id=demand_cfg_by_run_id,
        demand_yaml_paths_by_run_id=demand_yaml_paths_by_run_id,
        init_vars=init_vars,
        overrides_resources=overrides_resources,
    )

    xlsx_memory_write_node_ids_by_run_id = _append_write_nodes_from_runs(
        wf_obj,
        demand_cfg_by_run_id=demand_cfg_by_run_id,
        nodes=nodes,
        edges=edges,
        effective_books=effective_books,
        effective_files=effective_files,
        overrides_outputs=overrides_outputs,
        default_book_id=default_book_id,
    )

    _inject_xlsx_memory_write_dependencies(
        xlsx_memory_write_node_ids_by_run_id,
        direct_dependents_by_run_id,
        demand_node_pos_by_run_id,
        nodes,
        edges,
    )

    workflow_options = _build_workflow_options_ir(
        wf_obj,
        workflow_resources_wait=workflow_resources_wait,
        workflow_output_staging=workflow_output_staging,
    )

    artifacts = WorkflowArtifactsIr(slots_by_node_id=slots_by_node_id)
    resources_sorted = sorted(resources, key=lambda r: (str(r.resource_type), str(r.resource_id)))
    workflow_ir = WorkflowIr(
        nodes=tuple(nodes),
        edges=tuple(edges),
        options=workflow_options,
        resources=tuple(resources_sorted),
        artifacts=artifacts,
    )
    return WorkflowCompileResult(
        workflow_ir=workflow_ir,
        demand_configs_by_run_id=demand_cfg_by_run_id,
    )


def derive_cache_pool_consumers(
    workflow_ir: WorkflowIr,
    *,
    demand_configs_by_run_id: Mapping[str, DemandConfig],
) -> Tuple[Dict[str, FrozenSet[Tuple[str, str]]], Dict[Tuple[str, str], FrozenSet[str]]]:
    """基于 `workflow IR` + `demand YAML` 推导缓存消费者集合上界.

    `v0`: 仅覆盖 `cache_mode=preload_forever` 的 `sources`,按 `(kind, source_id)` 聚合.
    """

    logical_keys_by_node_id: Dict[str, FrozenSet[Tuple[str, str]]] = {}
    consumers_by_logical_key: Dict[Tuple[str, str], Set[str]] = {}

    for node in workflow_ir.nodes:
        node_id = str(node.node_id)
        keys: Set[Tuple[str, str]] = set()
        config = demand_configs_by_run_id.get(node_id) if isinstance(node, WorkflowNodeIr) else None
        if config is not None:
            for source_id, source in config.sources.items():
                if str(source.cache_mode or "") != "preload_forever":
                    continue
                logical_key = ("preload_forever", str(source_id))
                keys.add(logical_key)
                consumers_by_logical_key.setdefault(logical_key, set()).add(node_id)

        logical_keys_by_node_id[node_id] = frozenset(keys)

    consumers_frozen = {key: frozenset(sorted(node_ids)) for key, node_ids in consumers_by_logical_key.items()}
    return logical_keys_by_node_id, consumers_frozen


__all__ = (
    "compile_workflow_ir",
    "derive_cache_pool_consumers",
)
