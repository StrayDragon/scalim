"""`RunOverrides` 强类型覆盖项解析与叠加的 `SSOT`.

本模块将运行时覆盖项 (`RunOverrides`) 的解析/校验集中到一个地方 (`SSOT`), 同时服务于:
- 单 `demand` 的运行时编译 (`scalim.dsl.yaml_dsl.runtime.compiler`)
- `workflow` 编译 (`scalim.dsl.yaml_dsl.workflow_compile`)

约束:
- 运行时必须保持 `Python 3.6` 兼容。
- 覆盖项非法时必须抛 `ScalimWorkflowConfigError`, 并提供稳定可定位的 `.path`。
"""

import os
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple, cast

from ....vendor.dataclassesx import replace
from ....workflow.errors import ScalimWorkflowConfigError
from ..init_var_nodes import InitVarRef, OptionalPathNode, parse_init_var_ref
from ..runtime.contracts import (
    BookExportXlsxOverride,
    BookResourceOverride,
    FileResourceOverride,
    OutputExtraSheetOverride,
    OutputExtrasOverride,
    OutputOverride,
    OutputsDefaultsOverride,
    OutputToOverride,
    OutputWriteOverride,
    ResourcesOverride,
)
from ..schema_dsl.constants import DEFAULT_OUTPUT_ENCODING
from ..schema_dsl.models import (
    BookBudgetConfig,
    BookConfig,
    BookExportXlsxConfig,
    DemandConfig,
    FileConfig,
    OutputExtraSheetConfig,
    OutputTargetConfig,
    OutputToConfig,
    OutputWriteConfig,
    ResourcesConfig,
)
from ..schema_dsl.output_enums import (
    BOOK_KINDS,
    FILE_KINDS,
)
from .patch_apply import (
    as_bool as _patch_as_bool,
)
from .patch_apply import (
    as_opt_mapping as _patch_as_opt_mapping,
)
from .patch_apply import (
    as_opt_str as _patch_as_opt_str,
)
from .patch_apply import (
    assert_no_unknown_keys as _patch_assert_no_unknown_keys,
)
from .validation_contracts import validate_output_name as _validate_output_name_ssot

__all__ = ()

_OUTPUT_HEADER_BY_ENUM: Tuple[str, ...] = ("field_id", "name")


def _as_non_empty_str(value: Any, *, path: str) -> str:
    if not isinstance(value, str):
        msg = "{} must be a non-empty string".format(path)
        raise ScalimWorkflowConfigError(msg, path=str(path))
    v = str(value).strip()
    if not v:
        msg = "{} must be a non-empty string".format(path)
        raise ScalimWorkflowConfigError(msg, path=str(path))
    return v


def _as_opt_non_empty_str_or_pathlike(value: Any, *, path: str) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, os.PathLike):
        v = str(os.fspath(value)).strip()
        if not v:
            msg = "{} must not be empty".format(path)
            raise ScalimWorkflowConfigError(msg, path=str(path))
        return v
    if isinstance(value, str):
        v = str(value).strip()
        if not v:
            msg = "{} must not be empty".format(path)
            raise ScalimWorkflowConfigError(msg, path=str(path))
        return v
    msg = "{} must be a string or os.PathLike".format(path)
    raise ScalimWorkflowConfigError(msg, path=str(path))


def _as_opt_path_or_init_var(value: Any, *, path: str) -> OptionalPathNode:
    """校验可选的 `{ $init_var: ... }` / 路径类值。

    返回规范化后的表示:
    - 缺失时返回 `None`
    - `init_var` 映射返回 `InitVarRef`
    - 字符串或 `os.PathLike` 返回去除首尾空白后的 `str`
    """

    if value is None:
        return None

    if isinstance(value, InitVarRef):
        return value

    if isinstance(value, dict):
        return parse_init_var_ref(cast("Dict[str, Any]", value), path=str(path))  # pragma: allow-cast mapping narrowing

    if isinstance(value, os.PathLike):
        v = str(os.fspath(value)).strip()
        if not v:
            msg = "{} must not be empty".format(path)
            raise ScalimWorkflowConfigError(msg, path=str(path))
        return v

    if isinstance(value, str):
        v = str(value).strip()
        if not v:
            msg = "{} must not be empty".format(path)
            raise ScalimWorkflowConfigError(msg, path=str(path))
        return v

    msg = "{} must be a string, os.PathLike, InitVarRef, or {{$init_var: <name>}}".format(path)
    raise ScalimWorkflowConfigError(msg, path=str(path))


def parse_outputs_defaults_book_id(defaults: Optional[Any], *, path: str) -> Optional[str]:
    if defaults is None:
        return None
    if not isinstance(defaults, OutputsDefaultsOverride):
        msg = "{} must be an OutputsDefaultsOverride".format(path)
        raise ScalimWorkflowConfigError(msg, path=str(path))
    book_id = str(defaults.to.book or "").strip()
    if not book_id:
        msg = "{}.to.book is required".format(path)
        raise ScalimWorkflowConfigError(msg, path="{}.to.book".format(path))
    return str(book_id)


def apply_default_book_binding_to_outputs(
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


def _parse_typed_overrides_output_to(raw: OutputToOverride) -> OutputToConfig:
    file_id = str(raw.file or "").strip() if raw.file is not None else None
    book_id = str(raw.book or "").strip() if raw.book is not None else None
    sheet = str(raw.sheet or "").strip() if raw.sheet is not None else None
    if file_id == "":
        file_id = None
    if book_id == "":
        book_id = None
    if sheet == "":
        sheet = None
    return OutputToConfig(file=file_id, book=book_id, sheet=sheet)


def _parse_typed_overrides_output_write(raw: OutputWriteOverride, *, path: str) -> OutputWriteConfig:
    include_header = raw.include_header
    if include_header is not None and not isinstance(include_header, bool):
        msg = "{}.include_header must be a boolean".format(path)
        raise ScalimWorkflowConfigError(msg, path="{}.include_header".format(path))

    header_fields_output_by = str(raw.header_fields_output_by).strip() if raw.header_fields_output_by is not None else None
    header_fields_output_by = header_fields_output_by or None
    if header_fields_output_by is not None and header_fields_output_by not in _OUTPUT_HEADER_BY_ENUM:
        msg = "{}.header_fields_output_by={!r} is invalid; expected one of: {}".format(
            path, header_fields_output_by, ", ".join(_OUTPUT_HEADER_BY_ENUM)
        )
        raise ScalimWorkflowConfigError(msg, path="{}.header_fields_output_by".format(path))

    return OutputWriteConfig(include_header=include_header, header_fields_output_by=header_fields_output_by)


def parse_output_extra_sheet_override(
    raw: Any,
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
        msg = "{}.path must be a string or os.PathLike".format(path)
        raise ScalimWorkflowConfigError(msg, path="{}.path".format(path))
    resolved_path = _as_opt_non_empty_str_or_pathlike(raw_path, path="{}.path".format(path)) if raw_path is not None else None

    allow_formulas = raw.allow_formulas
    if allow_formulas is not None and not isinstance(allow_formulas, bool):
        msg = "{}.allow_formulas must be a bool".format(path)
        raise ScalimWorkflowConfigError(msg, path="{}.allow_formulas".format(path))

    return OutputExtraSheetConfig(
        path=resolved_path,
        sheet=sheet,
        allow_formulas=allow_formulas,
    )


def compile_output_extras_override(
    extras: Optional[Any],
    *,
    path: str,
) -> Tuple[Optional[OutputExtraSheetConfig], Optional[OutputExtraSheetConfig]]:
    if extras is None:
        return None, None
    if not isinstance(extras, OutputExtrasOverride):
        msg = "{} must be an OutputExtrasOverride".format(path)
        raise ScalimWorkflowConfigError(msg, path=str(path))

    meta = parse_output_extra_sheet_override(extras.meta, path="{}.meta".format(path))
    audit = parse_output_extra_sheet_override(extras.audit, path="{}.audit".format(path))
    return meta, audit


def parse_overrides_outputs_targets(  # noqa: C901, PLR0912, PLR0915  # pragma: allow-c901 plan: c4
    overrides: Sequence[OutputOverride],
    *,
    path: str,
    default_book_id: Optional[str],
    default_book_ref: str,
    known_field_ids: Optional[Set[str]],
) -> Tuple[OutputTargetConfig, ...]:
    """将强类型 `RunOverrides.outputs` 解析为有效的 `OutputTargetConfig` 列表。

    若提供 `known_field_ids`, 会校验 `fields` 中引用的 `field_id` 是否存在。
    """

    if not isinstance(overrides, tuple) and not isinstance(overrides, list):
        msg = "{} must be a sequence of OutputOverride".format(path)
        raise ScalimWorkflowConfigError(msg, path=str(path))
    if not overrides:
        msg = "{} cannot be empty".format(path)
        raise ScalimWorkflowConfigError(msg, path=str(path))

    seen_names: Set[str] = set()
    parsed: List[OutputTargetConfig] = []

    for idx, item in enumerate(overrides):
        if not isinstance(item, OutputOverride):
            msg = "{}.{} must be an OutputOverride".format(path, idx)
            raise ScalimWorkflowConfigError(msg, path="{}.{}".format(path, idx))

        name = str(item.name or "").strip()
        try:
            _validate_output_name_ssot(name, path="{}.{}.name".format(path, idx))
        except ValueError as exc:
            raise ScalimWorkflowConfigError(str(exc), path="{}.{}.name".format(path, idx)) from exc
        if name in seen_names:
            msg = "{} has duplicate output name: {}".format(path, name)
            raise ScalimWorkflowConfigError(msg, path=str(path))
        seen_names.add(name)

        fields = item.fields
        if not isinstance(fields, tuple):
            msg = "{}.{}.fields must be a tuple[str, ...]".format(path, idx)
            raise ScalimWorkflowConfigError(msg, path="{}.{}.fields".format(path, idx))
        if not fields:
            msg = "{}.{}.fields must not be empty".format(path, idx)
            raise ScalimWorkflowConfigError(msg, path="{}.{}.fields".format(path, idx))

        field_ids: List[str] = []
        for field_idx, field_id_raw in enumerate(fields):
            if not isinstance(field_id_raw, str):
                msg = "{}.{}.fields.{} must be a field_id string".format(path, idx, field_idx)
                raise ScalimWorkflowConfigError(msg, path="{}.{}.fields.{}".format(path, idx, field_idx))
            field_id = field_id_raw.strip()
            if not field_id:
                msg = "{}.{}.fields.{} must not be empty".format(path, idx, field_idx)
                raise ScalimWorkflowConfigError(msg, path="{}.{}.fields.{}".format(path, idx, field_idx))
            field_ids.append(field_id)

        if known_field_ids is not None:
            unknown_fields = [fid for fid in field_ids if fid not in known_field_ids]
            if unknown_fields:
                msg = "{}.{}.fields reference unknown fields: {}".format(path, idx, ", ".join(sorted(set(unknown_fields))))
                raise ScalimWorkflowConfigError(msg, path="{}.{}.fields".format(path, idx))

        to_override = item.to
        if not isinstance(to_override, OutputToOverride):
            msg = "{}.{}.to must be an OutputToOverride".format(path, idx)
            raise ScalimWorkflowConfigError(msg, path="{}.{}.to".format(path, idx))
        to_cfg = _parse_typed_overrides_output_to(to_override)

        write_cfg = None
        if item.write is not None:
            write_override = item.write
            if not isinstance(write_override, OutputWriteOverride):
                msg = "{}.{}.write must be an OutputWriteOverride".format(path, idx)
                raise ScalimWorkflowConfigError(msg, path="{}.{}.write".format(path, idx))
            write_cfg = _parse_typed_overrides_output_write(write_override, path="{}.{}.write".format(path, idx))

        file_id = str(to_cfg.file or "").strip() if to_cfg.file is not None else ""
        book_id = str(to_cfg.book or "").strip() if to_cfg.book is not None else ""
        sheet = str(to_cfg.sheet or "").strip() if to_cfg.sheet is not None else ""

        if file_id:
            if book_id:
                msg = "{}.{}.to must declare exactly one of to.file or to.book".format(path, idx)
                raise ScalimWorkflowConfigError(msg, path="{}.{}.to".format(path, idx))
            if sheet:
                msg = "{}.{}.to.sheet is not allowed with to.file".format(path, idx)
                raise ScalimWorkflowConfigError(msg, path="{}.{}.to.sheet".format(path, idx))
        else:
            effective_book_id = book_id or str(default_book_id or "").strip()
            if not effective_book_id:
                msg = ("Missing output destination for {}.{}.to; set {}.{}.to.book explicitly or provide {}.").format(
                    path, idx, path, idx, default_book_ref
                )
                raise ScalimWorkflowConfigError(msg, path="{}.{}.to".format(path, idx))
            if book_id != effective_book_id:
                to_cfg = replace(to_cfg, book=str(effective_book_id))

        parsed.append(
            OutputTargetConfig(
                name=str(name),
                from_=None,
                to=to_cfg,
                write=write_cfg,
                fields=tuple(field_ids),
                where=None,
                aggregate=None,
                requires=(),
            )
        )

    return tuple(parsed)


def _apply_optional_book_export_xlsx_patch(
    base: Optional[BookExportXlsxConfig],
    value: Any,
    *,
    path: str,
) -> Optional[BookExportXlsxConfig]:
    patch = _patch_as_opt_mapping(value, path="{}.export_xlsx".format(path))
    if patch is None:
        # 显式指定 `None` 表示清空可选的 `export_xlsx` 补丁。
        return None

    if "write_lock" in patch:
        msg = (
            "{}.export_xlsx.write_lock was removed; migrate to versioned outputs and locate results via <root>/manifest/latest.json".format(
                path
            )
        )
        raise ScalimWorkflowConfigError(msg, path="{}.export_xlsx.write_lock".format(path))

    allowed_keys = {"path", "allow_formulas"}
    _patch_assert_no_unknown_keys(patch, allowed_keys=allowed_keys, path="{}.export_xlsx".format(path))

    raw_path = patch.get("path")
    if raw_path is not None:
        export_path = _as_opt_path_or_init_var(raw_path, path="{}.export_xlsx.path".format(path))
    else:
        export_path = base.path if base is not None else None

    if export_path is None:
        msg = "{}.export_xlsx.path is required when creating export_xlsx".format(path)
        raise ScalimWorkflowConfigError(msg, path="{}.export_xlsx.path".format(path))

    allow_formulas = bool(base.allow_formulas) if base is not None else True
    if "allow_formulas" in patch:
        allow_formulas = _patch_as_bool(patch.get("allow_formulas"), path="{}.export_xlsx.allow_formulas".format(path))

    return BookExportXlsxConfig(path=export_path, allow_formulas=bool(allow_formulas))


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

    if kind == "xlsx_file":
        if book_path is None or (isinstance(book_path, str) and not str(book_path).strip()):
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
        if book_path is not None:
            msg = "{}.path is not allowed for kind=xlsx_memory".format(path)
            raise ScalimWorkflowConfigError(msg, path="{}.path".format(path))
        if allow_formulas:
            msg = "{}.allow_formulas is not allowed for kind=xlsx_memory".format(path)
            raise ScalimWorkflowConfigError(msg, path="{}.allow_formulas".format(path))
        return

    msg = "{}.kind={!r} is invalid; expected one of: {}".format(path, kind, ", ".join(BOOK_KINDS))
    raise ScalimWorkflowConfigError(msg, path="{}.kind".format(path))


def apply_book_resource_override(
    base: Optional[BookConfig],
    override: BookResourceOverride,
    *,
    path: str,
) -> BookConfig:
    patch = _book_resource_override_to_patch(override)
    return _apply_book_patch(base, patch, path=str(path))


def _patch_set_if_not_none(patch: Dict[str, Any], key: str, value: Any) -> None:
    if value is None:
        return
    patch[str(key)] = value


def _book_export_xlsx_override_to_patch(override: BookExportXlsxOverride) -> Dict[str, Any]:
    patch: Dict[str, Any] = {}
    _patch_set_if_not_none(patch, "path", override.path)
    _patch_set_if_not_none(patch, "allow_formulas", override.allow_formulas)
    return patch


def _book_resource_override_to_patch(override: BookResourceOverride) -> Dict[str, Any]:
    patch: Dict[str, Any] = {}

    _patch_set_if_not_none(patch, "kind", override.kind)
    _patch_set_if_not_none(patch, "path", override.path)
    _patch_set_if_not_none(patch, "allow_formulas", override.allow_formulas)

    if override.export_xlsx is not None:
        patch["export_xlsx"] = _book_export_xlsx_override_to_patch(override.export_xlsx)

    return patch


def _apply_book_patch(
    base: Optional[BookConfig],
    patch: Mapping[str, Any],
    *,
    path: str,
) -> BookConfig:
    kind = str(base.kind or "").strip() if base is not None else ""
    book_path: Any = base.path if base is not None else None
    budget = base.budget if base is not None else None
    export_xlsx = base.export_xlsx if base is not None else None
    allow_formulas = bool(base.allow_formulas) if base is not None else False
    write_defaults = base.write_defaults if base is not None else None

    if "write_defaults" in patch:
        msg = (
            "{}.write_defaults was removed from RunOverrides.resources. "
            "Migration: configure BookWritePolicy via DemandRunOptions.resources_policy "
            "or WorkflowRunOptions.resources_policy (Python SSOT)."
        ).format(path)
        raise ScalimWorkflowConfigError(msg, path="{}.write_defaults".format(path))
    if "budget" in patch:
        msg = (
            "{}.budget was removed from RunOverrides.resources. "
            "Migration: configure BookBudgetPolicy via DemandRunOptions.resources_policy "
            "or WorkflowRunOptions.resources_policy (Python SSOT)."
        ).format(path)
        raise ScalimWorkflowConfigError(msg, path="{}.budget".format(path))

    allowed_keys = {"kind", "path", "export_xlsx", "allow_formulas"}
    _patch_assert_no_unknown_keys(patch, allowed_keys=allowed_keys, path=path)

    if "kind" in patch:
        kind = _as_non_empty_str(patch.get("kind"), path="{}.kind".format(path))
    if "path" in patch:
        book_path = _as_opt_path_or_init_var(patch.get("path"), path="{}.path".format(path))
    if "allow_formulas" in patch:
        allow_formulas = _patch_as_bool(patch.get("allow_formulas"), path="{}.allow_formulas".format(path))
    if "export_xlsx" in patch:
        export_xlsx = _apply_optional_book_export_xlsx_patch(export_xlsx, patch.get("export_xlsx"), path=path)

    if base is None and "allow_formulas" not in patch and str(kind) == "xlsx_file":
        allow_formulas = True

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


def apply_file_resource_override(
    base: Optional[FileConfig],
    override: FileResourceOverride,
    *,
    path: str,
) -> FileConfig:
    patch: Dict[str, Any] = {}
    if override.kind is not None:
        patch["kind"] = override.kind
    if override.path is not None:
        patch["path"] = override.path
    if override.encoding is not None:
        patch["encoding"] = override.encoding
    return _apply_file_patch(base, patch, path=str(path))


def _apply_file_patch(base: Optional[FileConfig], patch: Mapping[str, Any], *, path: str) -> FileConfig:
    allowed_keys = {"kind", "path", "encoding"}
    unknown = sorted({str(k) for k in patch} - allowed_keys)
    if unknown:
        msg = "{} contains unknown keys: {}".format(path, ", ".join(unknown))
        raise ScalimWorkflowConfigError(msg, path=str(path))

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

    if "path" in patch:
        file_path = _as_opt_path_or_init_var(patch.get("path"), path="{}.path".format(path))
    if file_path is None:
        msg = "{}.path is required for kind=csv_file".format(path)
        raise ScalimWorkflowConfigError(msg, path="{}.path".format(path))

    if "encoding" in patch:
        encoding = _patch_as_opt_str(patch.get("encoding"), path="{}.encoding".format(path)) or DEFAULT_OUTPUT_ENCODING

    return FileConfig(kind=str(kind), path=file_path, encoding=str(encoding))


def overlay_resources_override(
    config: DemandConfig,
    override: ResourcesOverride,
    *,
    path: str,
) -> DemandConfig:
    """对 `DemandConfig` 应用仅涉及 `IO` 的 `overrides.resources` 叠加。"""

    if not override.books and not override.files:
        return config

    base_resources = config.resources
    merged_books: Dict[str, BookConfig] = dict(base_resources.books) if base_resources is not None else {}
    merged_files: Dict[str, FileConfig] = dict(base_resources.files) if base_resources is not None else {}

    if override.books:
        for raw_book_id, book_override in override.books.items():
            if not isinstance(raw_book_id, str) or not str(raw_book_id).strip():
                msg = "{}.books keys must be non-empty strings".format(path)
                raise ScalimWorkflowConfigError(msg, path="{}.books".format(path))
            book_id = str(raw_book_id).strip()
            if not isinstance(book_override, BookResourceOverride):
                msg = "{}.books.{} must be a BookResourceOverride".format(path, book_id)
                raise ScalimWorkflowConfigError(msg, path="{}.books.{}".format(path, book_id))
            merged_books[book_id] = apply_book_resource_override(
                merged_books.get(book_id),
                book_override,
                path="{}.books.{}".format(path, book_id),
            )

    if override.files:
        for raw_file_id, file_override in override.files.items():
            if not isinstance(raw_file_id, str) or not str(raw_file_id).strip():
                msg = "{}.files keys must be non-empty strings".format(path)
                raise ScalimWorkflowConfigError(msg, path="{}.files".format(path))
            file_id = str(raw_file_id).strip()
            if not isinstance(file_override, FileResourceOverride):
                msg = "{}.files.{} must be a FileResourceOverride".format(path, file_id)
                raise ScalimWorkflowConfigError(msg, path="{}.files.{}".format(path, file_id))
            merged_files[file_id] = apply_file_resource_override(
                merged_files.get(file_id),
                file_override,
                path="{}.files.{}".format(path, file_id),
            )

    return replace(config, resources=ResourcesConfig(books=merged_books, files=merged_files))
