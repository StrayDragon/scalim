"""`YAML DSL` 校验服务层(内部).

说明:
- 将 `scalim-cli yaml-dsl validate` 的校验流水线下沉为可复用服务层
- 服务层仅负责产生结构化 `payload`,不做 `CLI` 文本渲染
- 运行时需兼容 `Python 3.6`
"""

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple, cast

from ...exceptions import safe_error_message, safe_error_type
from ...vendor.dataclassesx import dataclass, field
from ._internal.config_parsing.error_envelope import ErrorEnvelope, ScalimYamlValidationError
from ._internal.config_parsing.imports import ScalimYamlImportExpansionError, contains_import_syntax, expand_imports_inplace
from ._internal.config_parsing.unknown_fields import UnknownFieldIssue
from ._internal.config_parsing.validator import ConfigValidator
from ._internal.config_parsing.validators.issues import ValidationIssue
from ._internal.config_parsing.yaml_load import (
    YamlLocationIndex,
    envelope_from_validation_issue,
    error_loc_for_yaml_path,
    load_yaml_mapping_text,
)
from .workflow_config import load_workflow_config_from_mapping
from .workflow_paths import resolve_workflow_demand_path
from .workflow_types import ScalimWorkflowConfigError

__all__ = ()


@dataclass
class ValidationPayload:
    mode: str
    """校验模式(例如 `validator`/`schema`)."""

    ok: bool
    """是否通过校验."""

    yaml_path: Optional[str] = None
    """可选:被校验的 `YAML` 文件路径."""

    schema_path: Optional[str] = None
    """可选:使用的 `JSON Schema` 文件路径."""

    errors: List[ErrorEnvelope] = field(default_factory=list)
    """错误列表."""

    warnings: List[ErrorEnvelope] = field(default_factory=list)
    """告警列表."""

    def as_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "mode": self.mode,
            "ok": self.ok,
            "errors": [issue.as_dict() for issue in self.errors],
            "warnings": [issue.as_dict() for issue in self.warnings],
        }
        if self.yaml_path is not None:
            payload["yaml_path"] = self.yaml_path
        if self.schema_path is not None:
            payload["schema_path"] = self.schema_path
        return payload


@dataclass
class WorkflowValidationPayload:
    mode: str
    ok: bool
    workflow_yaml_path: str
    results: List[ValidationPayload] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "ok": self.ok,
            "workflow_yaml_path": self.workflow_yaml_path,
            "results": [item.as_dict() for item in self.results],
        }


@dataclass
class DemandValidationResult:
    payload: ValidationPayload
    source_lines: Optional[List[str]]


@dataclass
class WorkflowValidationResult:
    payload: WorkflowValidationPayload
    workflow_payload: ValidationPayload
    workflow_source_lines: Optional[List[str]]
    demand_results: List[DemandValidationResult] = field(default_factory=list)


LEGACY_FIELDS = {
    "relations_sql_like",
    "relations_graph",
    "foreign_key",
    "target",
    "from",
    "via",
    "column",
    "pk",
    "pk_transform",
    "derived",
    "key_transform",
    "primary",
}


def _collect_legacy_fields(
    errors: List[ErrorEnvelope],
    data: Dict[str, Any],
    prefix: Optional[str],
    *,
    source_path: str,
    locations: YamlLocationIndex,
) -> None:
    for key in data:
        if key not in LEGACY_FIELDS:
            continue
        path = "{}.{}".format(prefix, key) if prefix else str(key)
        errors.append(
            ErrorEnvelope(
                code="yaml_legacy_field",
                message="Legacy field '{}' is not allowed".format(key),
                source_path=source_path,
                path=path,
                loc=error_loc_for_yaml_path(path, locations),
            )
        )


def find_legacy_field_errors(
    yaml_data: Dict[str, Any],
    *,
    source_path: str,
    locations: YamlLocationIndex,
) -> List[ErrorEnvelope]:
    errors: List[ErrorEnvelope] = []

    _collect_legacy_fields(errors, yaml_data, None, source_path=source_path, locations=locations)

    sources = yaml_data.get("sources", {})
    if isinstance(sources, dict):
        sources_dict = cast("Dict[str, Any]", sources)  # pragma: allow-cast yaml mapping typed narrowing for legacy field scan
        for source_id, source_data in sources_dict.items():
            if not isinstance(source_data, dict):
                continue
            source_data_dict = cast("Dict[str, Any]", source_data)  # pragma: allow-cast yaml mapping typed narrowing for legacy field scan
            _collect_legacy_fields(
                errors,
                source_data_dict,
                "sources.{}".format(source_id),
                source_path=source_path,
                locations=locations,
            )

    fields = yaml_data.get("fields", {})
    if isinstance(fields, dict):
        fields_dict = cast("Dict[str, Any]", fields)  # pragma: allow-cast yaml mapping typed narrowing for legacy field scan
        for field_id, field_data in fields_dict.items():
            if not isinstance(field_data, dict):
                continue
            field_data_dict = cast("Dict[str, Any]", field_data)  # pragma: allow-cast yaml mapping typed narrowing for legacy field scan
            _collect_legacy_fields(
                errors,
                field_data_dict,
                "fields.{}".format(field_id),
                source_path=source_path,
                locations=locations,
            )

    return errors


def issues_to_rows(
    issues: Iterable[object],
    *,
    source_path: str,
    locations: YamlLocationIndex,
    default_code: str,
) -> List[ErrorEnvelope]:
    rows: List[ErrorEnvelope] = []
    for issue in issues:
        if isinstance(issue, ErrorEnvelope):
            rows.append(issue)
            continue
        if isinstance(issue, ValidationIssue):
            rows.append(
                envelope_from_validation_issue(
                    issue,
                    source_path=source_path,
                    locations=locations,
                    default_code=default_code,
                )
            )
            continue
        if isinstance(issue, UnknownFieldIssue):
            path = str(issue.path or "(root)")
            rows.append(
                ErrorEnvelope(
                    code=str(default_code),
                    message=str(issue.message),
                    source_path=source_path,
                    path=path,
                    loc=error_loc_for_yaml_path(path, locations),
                    suggestions=tuple(issue.suggestions),
                )
            )
            continue
        rows.append(
            ErrorEnvelope(
                code=str(default_code),
                message=str(issue),
                source_path=source_path,
                path="(root)",
                loc=error_loc_for_yaml_path("(root)", locations),
            )
        )
    return rows


def find_removed_outputs_defaults_errors(
    yaml_data: Optional[Dict[str, Any]],
    *,
    source_path: str,
    locations: Optional[YamlLocationIndex],
    default_code: str,
) -> List[ErrorEnvelope]:
    if not isinstance(yaml_data, dict) or "outputs_defaults" not in yaml_data:
        return []
    path = "outputs_defaults"
    loc = None if locations is None else error_loc_for_yaml_path(path, locations)
    return [
        ErrorEnvelope(
            code=default_code,
            message=(
                "outputs_defaults was removed; move the book binding to each Excel output's `outputs[*].to.book`. "
                "Reuse it with YAML anchors (`_templates`) or `$import` if needed."
            ),
            source_path=source_path,
            path=path,
            loc=loc,
        )
    ]


def extract_demand_book_ids(yaml_data: Optional[Dict[str, Any]]) -> Set[str]:
    if not isinstance(yaml_data, dict):
        return set()
    resources_obj = yaml_data.get("resources")
    if not isinstance(resources_obj, dict):
        return set()
    resources = cast("Dict[str, Any]", resources_obj)  # pragma: allow-cast yaml mapping typed narrowing
    books_obj = resources.get("books")
    if not isinstance(books_obj, dict):
        return set()
    books = cast("Dict[str, Any]", books_obj)  # pragma: allow-cast yaml mapping typed narrowing
    out: Set[str] = set()
    for raw_book_id in books:
        if not isinstance(raw_book_id, str):
            continue
        bid = str(raw_book_id or "").strip()
        if bid:
            out.add(bid)
    return out


def _extract_output_book_ref(item: Dict[str, Any], *, idx: int) -> Tuple[str, str]:
    to_raw_obj = item.get("to")
    if isinstance(to_raw_obj, dict):
        to_raw = cast("Dict[str, Any]", to_raw_obj)  # pragma: allow-cast yaml mapping typed narrowing
        book_raw = to_raw.get("book")
        if isinstance(book_raw, str) and book_raw.strip():
            return "outputs.{}.to.book".format(int(idx)), str(book_raw).strip()
    return "outputs.{}.to.book".format(int(idx)), ""


def _extract_demand_outputs_book_refs(yaml_data: Optional[Dict[str, Any]]) -> List[Tuple[str, str]]:
    """提取需求 `outputs` 中绑定到 `books` 的引用信息.

    返回 `(ref_path, book_id)` 列表:
    - 对于包含 `container` 的 `outputs[*]`(`CSV` 文件输出),不返回任何项.
    - 若某个输出缺失有效 `book_id`,仍返回其 `ref_path`,但 `book_id` 为空字符串.
    """
    if not isinstance(yaml_data, dict):
        return []
    outputs_raw = yaml_data.get("outputs")
    if not isinstance(outputs_raw, list):
        return []
    outputs_list = cast("List[Any]", outputs_raw)  # pragma: allow-cast yaml outputs typed narrowing

    out: List[Tuple[str, str]] = []
    for idx, item in enumerate(outputs_list):
        if not isinstance(item, dict):
            continue
        item_dict = cast("Dict[str, Any]", item)  # pragma: allow-cast yaml mapping typed narrowing
        if item_dict.get("container") is not None:
            continue
        out.append(_extract_output_book_ref(item_dict, idx=int(idx)))

    return out


def find_demand_book_binding_errors(
    yaml_data: Optional[Dict[str, Any]],
    *,
    source_path: str,
    locations: Optional[YamlLocationIndex],
    available_book_ids: Optional[Set[str]],
    default_code: str,
) -> List[ErrorEnvelope]:
    if not isinstance(yaml_data, dict):
        return []

    available = tuple(sorted(available_book_ids or set()))
    errors: List[ErrorEnvelope] = []
    for ref_path, book_id in _extract_demand_outputs_book_refs(yaml_data):
        loc = None if locations is None else error_loc_for_yaml_path(ref_path, locations)
        if not book_id:
            errors.append(
                ErrorEnvelope(
                    code=default_code,
                    message=(
                        "Missing outputs to.book binding; set `outputs[*].to.book` explicitly. "
                        "Reuse the binding with YAML anchors (`_templates`) or `$import` if needed."
                    ),
                    source_path=source_path,
                    path=ref_path,
                    loc=loc,
                    suggestions=available,
                )
            )
            continue
        if available_book_ids is not None and book_id not in available_book_ids:
            errors.append(
                ErrorEnvelope(
                    code=default_code,
                    message=(
                        "Unknown book id referenced by outputs binding: {!r} "
                        "(declare resources.books.{} in demand or workflow.resources.books.{} in workflow)"
                    ).format(book_id, book_id, book_id),
                    source_path=source_path,
                    path=ref_path,
                    loc=loc,
                    suggestions=available,
                )
            )
    return errors


def _retry_enabled_missing_should_retry(retry_raw: object) -> bool:
    if not isinstance(retry_raw, dict):
        return False
    retry_dict = cast("Dict[str, Any]", retry_raw)  # pragma: allow-cast yaml retry mapping typed narrowing
    if retry_dict.get("enabled") is not True:
        return False
    should_retry_raw = retry_dict.get("should_retry")
    if not isinstance(should_retry_raw, str):
        return True
    return not bool(should_retry_raw.strip())


def find_retry_enabled_missing_should_retry_errors(
    yaml_data: Optional[Dict[str, Any]],
    *,
    source_path: str,
    locations: Optional[YamlLocationIndex],
    default_code: str,
) -> List[ErrorEnvelope]:
    if not isinstance(yaml_data, dict):
        return []

    def _add_error(path: str) -> ErrorEnvelope:
        loc = None if locations is None else error_loc_for_yaml_path(path, locations)
        return ErrorEnvelope(
            code=default_code,
            message=(
                "retry.enabled=true requires non-empty should_retry "
                "(provide it in YAML, or rely on runtime driver injection to supply it during compile/run)"
            ),
            source_path=source_path,
            path=path,
            loc=loc,
        )

    errors: List[ErrorEnvelope] = []
    if _retry_enabled_missing_should_retry(yaml_data.get("retry")):
        errors.append(_add_error("retry.should_retry"))

    main_source_raw = yaml_data.get("main_source")
    if isinstance(main_source_raw, dict):
        main_source_dict = cast("Dict[str, Any]", main_source_raw)  # pragma: allow-cast yaml main_source mapping typed narrowing
        if _retry_enabled_missing_should_retry(main_source_dict.get("retry")):
            errors.append(_add_error("main_source.retry.should_retry"))

    sources_raw = yaml_data.get("sources")
    if isinstance(sources_raw, dict):
        for source_id, source_cfg_raw in cast("Dict[str, Any]", sources_raw).items():  # pragma: allow-cast yaml sources typed narrowing
            if not isinstance(source_cfg_raw, dict):
                continue
            source_cfg_dict = cast("Dict[str, Any]", source_cfg_raw)  # pragma: allow-cast yaml source config mapping typed narrowing
            if _retry_enabled_missing_should_retry(source_cfg_dict.get("retry")):
                errors.append(_add_error("sources.{}.retry.should_retry".format(source_id)))

    return errors


def validate_demand_text(
    yaml_text: str,
    *,
    yaml_path: Path,
    schema_path: Path,
    validator: Optional[ConfigValidator] = None,
    allowed_yaml_roots: Optional[Sequence[Path]] = None,
    available_book_ids: Optional[Set[str]] = None,
) -> DemandValidationResult:
    source_lines: List[str] = yaml_text.splitlines()
    if not schema_path.exists():
        payload = ValidationPayload(
            mode="validate",
            ok=False,
            yaml_path=str(yaml_path),
            schema_path=str(schema_path),
            errors=[
                ErrorEnvelope(
                    code="schema_file_not_found",
                    message="Schema 文件不存在: {}".format(schema_path),
                    source_path=str(yaml_path),
                    path="(schema)",
                    loc=None,
                )
            ],
            warnings=[],
        )
        return DemandValidationResult(payload=payload, source_lines=source_lines)

    try:
        yaml_data_dict, locations, _lines = load_yaml_mapping_text(
            yaml_text,
            source_path=str(yaml_path),
            detect_duplicate_keys=True,
        )
    except ScalimYamlValidationError as exc:
        payload = ValidationPayload(
            mode="validate",
            ok=False,
            yaml_path=str(yaml_path),
            schema_path=str(schema_path),
            errors=list(exc.errors),
            warnings=list(exc.warnings),
        )
        return DemandValidationResult(payload=payload, source_lines=source_lines)

    try:
        if contains_import_syntax(yaml_data_dict):
            _ = expand_imports_inplace(yaml_data_dict, yaml_path=yaml_path, allowed_yaml_roots=allowed_yaml_roots)
    except ScalimYamlImportExpansionError as exc:
        logical_path = str(exc.logical_path or "(root)")
        errors = [
            ErrorEnvelope(
                code="yaml_import_expansion_error",
                message=str(exc),
                source_path=str(yaml_path),
                path=logical_path,
                loc=error_loc_for_yaml_path(logical_path, locations),
            )
        ]
        payload = ValidationPayload(
            mode="validate",
            ok=False,
            yaml_path=str(yaml_path),
            schema_path=str(schema_path),
            errors=errors,
            warnings=[],
        )
        return DemandValidationResult(payload=payload, source_lines=source_lines)

    demand_validator = validator or ConfigValidator(schema_path=str(schema_path))
    report = demand_validator.validate_report(
        yaml_data_dict,
        strict_unknown_fields=True,
        enable_jsonschema_validation=True,
    )
    errors = [
        envelope_from_validation_issue(
            issue,
            source_path=str(yaml_path),
            locations=locations,
            default_code="yaml_validate_error",
        )
        for issue in report.errors()
    ]
    warnings = [
        envelope_from_validation_issue(
            issue,
            source_path=str(yaml_path),
            locations=locations,
            default_code="yaml_validate_warning",
        )
        for issue in report.warnings()
    ]
    demand_book_ids = extract_demand_book_ids(yaml_data_dict)
    effective_book_ids = set(demand_book_ids)
    if available_book_ids is not None:
        effective_book_ids.update(available_book_ids)
    errors.extend(
        find_removed_outputs_defaults_errors(
            yaml_data_dict,
            source_path=str(yaml_path),
            locations=locations,
            default_code="yaml_validate_error",
        )
    )
    errors.extend(
        find_demand_book_binding_errors(
            yaml_data_dict,
            source_path=str(yaml_path),
            locations=locations,
            available_book_ids=effective_book_ids,
            default_code="yaml_validate_error",
        )
    )
    errors.extend(
        find_retry_enabled_missing_should_retry_errors(
            yaml_data_dict,
            source_path=str(yaml_path),
            locations=locations,
            default_code="yaml_validate_error",
        )
    )

    ok = not errors
    payload = ValidationPayload(
        mode="validate",
        ok=ok,
        yaml_path=str(yaml_path),
        schema_path=str(schema_path),
        errors=errors,
        warnings=warnings,
    )
    return DemandValidationResult(payload=payload, source_lines=source_lines)


def validate_demand_file(
    yaml_path: Path,
    *,
    schema_path: Path,
    validator: Optional[ConfigValidator] = None,
    allowed_yaml_roots: Optional[Sequence[Path]] = None,
    available_book_ids: Optional[Set[str]] = None,
) -> DemandValidationResult:
    if not schema_path.exists():
        payload = ValidationPayload(
            mode="validate",
            ok=False,
            yaml_path=str(yaml_path),
            schema_path=str(schema_path),
            errors=[
                ErrorEnvelope(
                    code="schema_file_not_found",
                    message="Schema 文件不存在: {}".format(schema_path),
                    source_path=str(yaml_path),
                    path="(schema)",
                    loc=None,
                )
            ],
            warnings=[],
        )
        return DemandValidationResult(payload=payload, source_lines=None)

    if not yaml_path.exists():
        errors = [
            ErrorEnvelope(
                code="yaml_file_not_found",
                message="YAML 文件不存在: {}".format(yaml_path),
                source_path=str(yaml_path),
                path="(file)",
                loc=None,
            )
        ]
        payload = ValidationPayload(
            mode="validate",
            ok=False,
            yaml_path=str(yaml_path),
            schema_path=str(schema_path),
            errors=errors,
            warnings=[],
        )
        return DemandValidationResult(payload=payload, source_lines=None)

    try:
        yaml_text = yaml_path.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        errors = [
            ErrorEnvelope(
                code="yaml_file_read_error",
                message="YAML 文件读取失败: {}".format(yaml_path),
                source_path=str(yaml_path),
                path="(file)",
                loc=None,
            )
        ]
        payload = ValidationPayload(
            mode="validate",
            ok=False,
            yaml_path=str(yaml_path),
            schema_path=str(schema_path),
            errors=errors,
            warnings=[],
        )
        return DemandValidationResult(payload=payload, source_lines=None)

    return validate_demand_text(
        yaml_text,
        yaml_path=yaml_path,
        schema_path=schema_path,
        validator=validator,
        allowed_yaml_roots=allowed_yaml_roots,
        available_book_ids=available_book_ids,
    )


def validate_workflow_text(
    workflow_text: str,
    *,
    yaml_path: Path,
    schema_path: Path,
    path_aliases: Optional[Dict[str, str]],
    allowed_yaml_roots: Optional[Sequence[Path]],
) -> WorkflowValidationResult:
    workflow_source_lines: List[str] = workflow_text.splitlines()
    if not schema_path.exists():
        workflow_payload = ValidationPayload(
            mode="workflow-validate",
            ok=False,
            yaml_path=str(yaml_path),
            errors=[
                ErrorEnvelope(
                    code="schema_file_not_found",
                    message="Schema 文件不存在: {}".format(schema_path),
                    source_path=str(yaml_path),
                    path="(schema)",
                    loc=None,
                )
            ],
            warnings=[],
        )
        payload = WorkflowValidationPayload(
            mode="workflow-validate",
            ok=False,
            workflow_yaml_path=str(yaml_path),
            results=[workflow_payload],
        )
        return WorkflowValidationResult(
            payload=payload,
            workflow_payload=workflow_payload,
            workflow_source_lines=workflow_source_lines,
            demand_results=[],
        )

    workflow_locations: YamlLocationIndex = {}
    workflow_errors: List[ErrorEnvelope] = []
    workflow_warnings: List[ErrorEnvelope] = []

    wf_config = None
    try:
        root, workflow_locations, _lines = load_yaml_mapping_text(
            workflow_text,
            source_path=str(yaml_path),
            detect_duplicate_keys=True,
        )
    except ScalimYamlValidationError as exc:
        workflow_errors.extend(list(exc.errors))
        workflow_warnings.extend(list(exc.warnings))
    else:
        try:
            wf_config = load_workflow_config_from_mapping(root)
        except ScalimWorkflowConfigError as exc:
            path = str(exc.path or "(root)")
            workflow_errors.append(
                ErrorEnvelope(
                    code="workflow_validate_error",
                    message=str(exc),
                    source_path=str(yaml_path),
                    path=path,
                    loc=error_loc_for_yaml_path(path, workflow_locations),
                )
            )
        except Exception as exc:  # noqa: BLE001
            safe_type = safe_error_type(exc)
            safe_msg = safe_error_message(exc) or ""
            workflow_errors.append(
                ErrorEnvelope(
                    code="workflow_validate_error",
                    message="Unexpected error: {}: {}".format(safe_type, safe_msg),
                    source_path=str(yaml_path),
                    path="(root)",
                    loc=error_loc_for_yaml_path("(root)", workflow_locations),
                )
            )

    demand_results: List[DemandValidationResult] = []

    demand_validator = ConfigValidator(schema_path=str(schema_path))
    if wf_config is not None:
        workflow_book_ids = set((wf_config.resources.books or {}).keys())
        for run_idx, run in enumerate(wf_config.runs):
            try:
                demand_path = resolve_workflow_demand_path(
                    str(run.demand),
                    workflow_yaml_path=str(yaml_path),
                    path_aliases=path_aliases,
                    run_id=str(run.id),
                    allowed_yaml_roots=allowed_yaml_roots,
                )
            except ScalimWorkflowConfigError as exc:
                wf_path = "workflow.runs.{}.demand".format(int(run_idx))
                workflow_errors.append(
                    ErrorEnvelope(
                        code="workflow_validate_error",
                        message=str(exc),
                        source_path=str(yaml_path),
                        path=wf_path,
                        loc=error_loc_for_yaml_path(wf_path, workflow_locations),
                    )
                )
                demand_results.append(
                    DemandValidationResult(
                        payload=ValidationPayload(
                            mode="validate",
                            ok=False,
                            yaml_path=str(run.demand),
                            schema_path=str(schema_path),
                            errors=[
                                ErrorEnvelope(
                                    code="demand_path_resolve_failed",
                                    message="Demand path resolve failed: {}".format(str(exc)),
                                    source_path=str(run.demand),
                                    path="(file)",
                                    loc=None,
                                )
                            ],
                            warnings=[],
                        ),
                        source_lines=None,
                    )
                )
                continue

            if not demand_path.exists():
                wf_path = "workflow.runs.{}.demand".format(int(run_idx))
                workflow_errors.append(
                    ErrorEnvelope(
                        code="demand_file_not_found",
                        message="Demand YAML 文件不存在: {}".format(demand_path),
                        source_path=str(yaml_path),
                        path=wf_path,
                        loc=error_loc_for_yaml_path(wf_path, workflow_locations),
                    )
                )

            demand_results.append(
                validate_demand_file(
                    demand_path,
                    schema_path=schema_path,
                    validator=demand_validator,
                    allowed_yaml_roots=allowed_yaml_roots,
                    available_book_ids=workflow_book_ids,
                )
            )

    workflow_ok = not workflow_errors
    workflow_payload = ValidationPayload(
        mode="workflow-validate",
        ok=workflow_ok,
        yaml_path=str(yaml_path),
        errors=workflow_errors,
        warnings=workflow_warnings,
    )

    results: List[ValidationPayload] = [workflow_payload]
    results.extend([item.payload for item in demand_results])

    ok = workflow_ok and all(item.payload.ok for item in demand_results)
    payload = WorkflowValidationPayload(
        mode="workflow-validate",
        ok=ok,
        workflow_yaml_path=str(yaml_path),
        results=results,
    )

    return WorkflowValidationResult(
        payload=payload,
        workflow_payload=workflow_payload,
        workflow_source_lines=workflow_source_lines,
        demand_results=demand_results,
    )


def validate_workflow_file(
    yaml_path: Path,
    *,
    schema_path: Path,
    path_aliases: Optional[Dict[str, str]],
    allowed_yaml_roots: Optional[Sequence[Path]],
) -> WorkflowValidationResult:
    workflow_text = yaml_path.read_text(encoding="utf-8")
    return validate_workflow_text(
        workflow_text,
        yaml_path=yaml_path,
        schema_path=schema_path,
        path_aliases=path_aliases,
        allowed_yaml_roots=allowed_yaml_roots,
    )
