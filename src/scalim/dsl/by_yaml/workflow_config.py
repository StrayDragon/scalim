import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple, Union, cast

from ...vendor.compact.importlibx import require_optional_dependency
from ...vendor.dataclassesx import dataclass
from ...vendor.dataclassesx import field as dataclass_field
from ._public_template_sandbox import validate_public_template_sandbox
from .config_parsing.allowed_paths import normalize_allowed_yaml_roots, validate_resolved_yaml_path_within_roots
from .config_parsing.template_precompile import maybe_precompile_yaml_text

if TYPE_CHECKING:
    import yaml
else:
    yaml = require_optional_dependency(
        "yaml",
        context="scalim.dsl.by_yaml.workflow",
        install_name="pyyaml",
    )


_FAILURE_POLICIES = ("all_fail", "primary_only")
_CACHE_POOL_CONFLICT_POLICIES = ("error", "separate", "warn")
_CACHE_POOL_RELEASE_POLICIES = ("dag_refcount", "workflow_end")
_CACHE_POOL_OVER_BUDGET_POLICIES = ("fail_fast", "evict_lru")
_CACHE_POOL_PIN_KINDS = ("preload_forever",)

_ALIAS_DEMAND_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):/(.+)$")

_INTERNAL_NODE_ID_PREFIX = "__wf__"
_RESOURCE_GROUP_KEYS = ("workbooks", "csvs", "sheetbooks")
_WRITE_INTENT_KEYS = ("workbook_sheet", "workbook_append", "csv_append", "sheetbook_sheet", "sheetbook_append")
_WRITE_INTENT_ON_CONFLICT_POLICIES = ("error", "overwrite", "skip")
_WRITE_INTENT_ALIGN_BY = ("field_id", "header")
_WRITE_INTENT_HEADER_POLICIES = ("once", "always", "never")
_WRITE_INTENT_ON_MISMATCH_POLICIES = ("error", "warn", "skip")
_EXCEL_SHEET_NAME_MAX_LEN = 31
_EXCEL_SHEET_NAME_INVALID_CHARS = frozenset(["\\", "/", "?", "*", "[", "]", ":"])


class WorkflowConfigError(ValueError):
    path: str

    def __init__(self, message: str, *, path: str = "") -> None:
        self.path = str(path or "")
        super(WorkflowConfigError, self).__init__(self._format(message))

    def _format(self, message: str) -> str:
        if not self.path:
            return str(message)
        return "{} (path={})".format(message, self.path)


def _safe_load_yaml_no_duplicates(text: str) -> object:
    """对 `yaml.safe_load` 增加重复 `key` 检测.

    需求: `workflow` 需要对资源 `id` 冲突等场景做提前校验; 这要求在解析阶段保留并检测重复 `key`.
    """

    class _Loader(yaml.SafeLoader):  # type: ignore[name-defined]
        pass

    def _construct_mapping(loader: object, node: object, deep: bool = False) -> Dict[object, object]:  # noqa: FBT001, FBT002
        mapping: Dict[object, object] = {}
        pairs = cast("Any", node).value
        for key_node, value_node in pairs:
            key = cast("Any", loader).construct_object(key_node, deep=deep)
            if key in mapping:
                msg = "Duplicate key in YAML mapping: {!r}".format(key)
                raise ValueError(msg)
            value = cast("Any", loader).construct_object(value_node, deep=deep)
            mapping[key] = value
        return mapping

    _Loader.add_constructor(  # type: ignore[attr-defined]
        cast("Any", yaml).resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        _construct_mapping,
    )
    return cast("Any", yaml).load(text, Loader=_Loader)


@dataclass(frozen=True)
class WorkflowWorkbookResource:
    path: str
    allow_formulas: bool = False


@dataclass(frozen=True)
class WorkflowCsvResource:
    path: str


@dataclass(frozen=True)
class WorkflowSheetbookBudget:
    max_sheets: int
    max_total_cells: int


@dataclass(frozen=True)
class WorkflowSheetbookExportXlsx:
    path: str
    write_lock: bool = False
    allow_formulas: bool = False


@dataclass(frozen=True)
class WorkflowSheetbookResource:
    budget: WorkflowSheetbookBudget
    export_xlsx: Optional[WorkflowSheetbookExportXlsx] = None


@dataclass(frozen=True)
class WorkflowResources:
    workbooks: Dict[str, WorkflowWorkbookResource] = dataclass_field(default_factory=dict)
    csvs: Dict[str, WorkflowCsvResource] = dataclass_field(default_factory=dict)
    sheetbooks: Dict[str, WorkflowSheetbookResource] = dataclass_field(default_factory=dict)


@dataclass(frozen=True)
class WorkflowWriteToWorkbookSheet:
    workbook: str
    sheet: str
    output: str
    on_conflict: str = "error"


@dataclass(frozen=True)
class WorkflowWriteToWorkbookAppend:
    workbook: str
    sheet: str
    output: str
    align_by: str = "field_id"
    header_policy: str = "once"
    on_mismatch: str = "error"


@dataclass(frozen=True)
class WorkflowWriteToCsvAppend:
    csv: str
    output: str
    header_policy: str = "once"
    on_mismatch: str = "error"


@dataclass(frozen=True)
class WorkflowWriteToSheetbookSheet:
    sheetbook: str
    sheet: str
    output: str
    on_conflict: str = "error"


@dataclass(frozen=True)
class WorkflowWriteToSheetbookAppend:
    sheetbook: str
    sheet: str
    output: str
    align_by: str = "field_id"
    header_policy: str = "once"
    on_mismatch: str = "error"


WorkflowWriteTo = Union[
    WorkflowWriteToWorkbookSheet,
    WorkflowWriteToWorkbookAppend,
    WorkflowWriteToCsvAppend,
    WorkflowWriteToSheetbookSheet,
    WorkflowWriteToSheetbookAppend,
]


@dataclass(frozen=True)
class WorkflowRun:
    id: str
    demand: str
    depends_on: Tuple[str, ...] = ()
    init_vars: Optional[Dict[str, object]] = None
    writes: Tuple[WorkflowWriteTo, ...] = ()


@dataclass(frozen=True)
class WorkflowCtxOptions:
    max_value_bytes: int = 65536
    max_bytes: int = 1048576


@dataclass(frozen=True)
class WorkflowOptions:
    max_concurrency: int = 1
    failure_policy: str = "all_fail"
    cache_pool: Optional["WorkflowCachePoolOptions"] = None
    ctx: WorkflowCtxOptions = dataclass_field(default_factory=WorkflowCtxOptions)


@dataclass(frozen=True)
class WorkflowCachePoolBudget:
    max_entries: int
    over_budget_policy: str


@dataclass(frozen=True)
class WorkflowCachePoolPin:
    kind: str
    source_id: str


@dataclass(frozen=True)
class WorkflowCachePoolOptions:
    conflict_policy: str
    release_policy: str
    budget: WorkflowCachePoolBudget
    pin: Tuple[WorkflowCachePoolPin, ...] = ()


@dataclass(frozen=True)
class WorkflowConfig:
    runs: Tuple[WorkflowRun, ...]
    options: WorkflowOptions
    resources: WorkflowResources = dataclass_field(default_factory=WorkflowResources)


def load_workflow_config(
    workflow_yaml_path: str,
    *,
    template_vars: Optional[Mapping[str, object]] = None,
    template_sandbox: str = "safe",
) -> WorkflowConfig:
    template_sandbox = validate_public_template_sandbox(template_sandbox)
    msg: str
    yaml_path = Path(str(workflow_yaml_path or "")).expanduser()
    try:
        text = yaml_path.read_text(encoding="utf-8")
    except Exception as exc:
        msg = "Failed to read workflow YAML: {}: {}".format(type(exc).__name__, exc)
        raise WorkflowConfigError(msg, path="(file)") from exc

    try:
        text = maybe_precompile_yaml_text(
            text,
            template_vars=template_vars,
            context_label="工作流 `YAML` 文件 `{}`".format(str(yaml_path)),
            template_sandbox=template_sandbox,
        )
    except ValueError as exc:
        raise WorkflowConfigError(str(exc), path="(file)") from exc

    try:
        loaded = _safe_load_yaml_no_duplicates(text)
    except Exception as exc:
        msg = "YAML parse error: {}: {}".format(type(exc).__name__, exc)
        raise WorkflowConfigError(msg, path="(root)") from exc

    if not isinstance(loaded, dict):
        msg = "workflow YAML root must be a mapping"
        raise WorkflowConfigError(msg, path="(root)")

    return load_workflow_config_from_mapping(cast("Dict[str, Any]", loaded))


def resolve_workflow_demand_path(
    demand: str,
    *,
    workflow_yaml_path: str,
    path_aliases: Optional[Mapping[str, str]] = None,
    run_id: Optional[str] = None,
    allowed_yaml_roots: Optional[Sequence[Union[str, Path]]] = None,
) -> Path:
    msg: str
    raw = str(demand or "").strip()
    if not raw:
        msg = "run.demand must be a non-empty string"
        raise WorkflowConfigError(msg, path="workflow.runs[*].demand")

    wf_path = Path(str(workflow_yaml_path or "")).expanduser().resolve(strict=False)
    base_dir = wf_path.parent

    roots: Tuple[Path, ...]
    try:
        roots = normalize_allowed_yaml_roots(allowed_yaml_roots, default_root=base_dir)
    except ValueError as exc:
        msg = "Invalid allowed_yaml_roots: {}".format(exc)
        if run_id:
            msg = "{} (run_id={})".format(msg, run_id)
        raise WorkflowConfigError(msg, path="workflow.runs[*].demand") from exc

    if raw.startswith("@/"):
        alias = "@"
        rel = raw[2:]
        return _resolve_alias_path(
            alias=alias,
            rel=rel,
            raw=raw,
            path_aliases=path_aliases,
            run_id=run_id,
            allowed_yaml_roots=roots,
        )

    m = _ALIAS_DEMAND_RE.match(raw)
    if m is not None:
        alias = m.group(1)
        rel = m.group(2)
        return _resolve_alias_path(
            alias=alias,
            rel=rel,
            raw=raw,
            path_aliases=path_aliases,
            run_id=run_id,
            allowed_yaml_roots=roots,
        )

    p = Path(raw).expanduser()
    resolved = p.resolve(strict=False) if p.is_absolute() else (base_dir / p).resolve(strict=False)

    try:
        validate_resolved_yaml_path_within_roots(
            raw_path=raw,
            base_dir=base_dir,
            resolved_path=resolved,
            allowed_yaml_roots=roots,
            context_label="workflow.runs[*].demand",
        )
    except ValueError as exc:
        msg = str(exc)
        if run_id:
            msg = "{} (run_id={})".format(msg, run_id)
        raise WorkflowConfigError(msg, path="workflow.runs[*].demand") from exc

    return resolved


def _resolve_alias_path(
    *,
    alias: str,
    rel: str,
    raw: str,
    path_aliases: Optional[Mapping[str, str]],
    run_id: Optional[str],
    allowed_yaml_roots: Sequence[Path],
) -> Path:
    msg: str
    aliases = path_aliases or {}
    base_raw = aliases.get(alias)
    if base_raw is None:
        msg = "Unknown path alias '{}' for demand path '{}'".format(alias, raw)
        if run_id:
            msg = "{} (run_id={})".format(msg, run_id)
        raise WorkflowConfigError(msg, path="workflow.runs[*].demand")
    base = Path(str(base_raw)).expanduser()
    rel_str = str(rel or "").lstrip("/")
    if not rel_str:
        msg = "Invalid demand alias path '{}'".format(raw)
        if run_id:
            msg = "{} (run_id={})".format(msg, run_id)
        raise WorkflowConfigError(msg, path="workflow.runs[*].demand")
    rel_path = Path(rel_str)
    resolved = (base / rel_path).resolve(strict=False)
    try:
        validate_resolved_yaml_path_within_roots(
            raw_path=raw,
            base_dir=base,
            resolved_path=resolved,
            allowed_yaml_roots=allowed_yaml_roots,
            context_label="workflow.runs[*].demand(alias={}, alias_base={})".format(alias, str(base)),
        )
    except ValueError as exc:
        msg = str(exc)
        if run_id:
            msg = "{} (run_id={})".format(msg, run_id)
        raise WorkflowConfigError(msg, path="workflow.runs[*].demand") from exc
    return resolved


def validate_workflow_yaml_text_json(
    yaml_text: str,
    strict_unknown_fields: bool = False,  # noqa: FBT001, FBT002
    schema_path: Optional[str] = None,
) -> str:
    """返回与 YAML DSL 编辑器的“精确校验器”兼容的 JSON 载荷(`Workflow` 版).

    注意:
    - `workflow` YAML 与 `demand` YAML 是两套语义;此校验器只做 `workflow` 语义校验.
    - 目前不基于 `schema_path` 做 `JSONSchema` 校验(结构校验建议交给 `YAML LSP`).
    """
    _ = (strict_unknown_fields, schema_path)
    payload = _validate_workflow_yaml_text(yaml_text)
    return json.dumps(payload, ensure_ascii=False)


def _validate_workflow_yaml_text(yaml_text: str) -> Dict[str, Any]:
    try:
        yaml_data = _safe_load_yaml_no_duplicates(yaml_text)
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "errors": [{"path": "(root)", "message": "YAML parse error: {}".format(exc)}],
            "warnings": [],
        }

    if yaml_data is None:
        return {
            "ok": False,
            "errors": [{"path": "(root)", "message": "YAML document is empty"}],
            "warnings": [],
        }

    if not isinstance(yaml_data, dict):
        return {
            "ok": False,
            "errors": [{"path": "(root)", "message": "workflow YAML root must be a mapping"}],
            "warnings": [],
        }

    try:
        _ = load_workflow_config_from_mapping(cast("Dict[str, Any]", yaml_data))
    except WorkflowConfigError as exc:
        return {
            "ok": False,
            "errors": [{"path": str(exc.path or "(root)"), "message": str(exc)}],
            "warnings": [],
        }

    return {"ok": True, "errors": [], "warnings": []}


def _validate_excel_sheet_name(value: str, *, path: str) -> None:
    """校验 `Excel` `sheet` 名合法性(用于 `sheetbook` 资源).

    注意: `workbook` 的 `sheet` 名限制主要由 `openpyxl` 约束,这里对 `sheetbook` 做显式 `fail-fast`.
    """
    msg: str
    name = str(value or "").strip()
    if not name:
        msg = "sheet name must be a non-empty string"
        raise WorkflowConfigError(msg, path=path)
    if len(name) > _EXCEL_SHEET_NAME_MAX_LEN:
        msg = "sheet name is too long (max_len={}): {!r}".format(_EXCEL_SHEET_NAME_MAX_LEN, name)
        raise WorkflowConfigError(msg, path=path)
    invalid = sorted(ch for ch in name if ch in _EXCEL_SHEET_NAME_INVALID_CHARS)
    if invalid:
        msg = "sheet name contains invalid characters: {!r}".format("".join(invalid))
        raise WorkflowConfigError(msg, path=path)


def _parse_run_depends_on(depends_on_raw: object, *, item_path: str) -> Tuple[str, ...]:
    msg: str
    depends_on: Tuple[str, ...] = ()
    if depends_on_raw is None:
        return depends_on

    if not isinstance(depends_on_raw, list):
        msg = "run.depends_on must be a list of strings"
        raise WorkflowConfigError(msg, path="{}.depends_on".format(item_path))

    depends_on_list: List[str] = []
    for dep_idx, dep in enumerate(cast("List[Any]", depends_on_raw)):
        dep_path = "{}.depends_on.{}".format(item_path, dep_idx)
        dep_id = str(dep or "").strip() if isinstance(dep, str) else ""
        if not dep_id:
            msg = "run.depends_on items must be non-empty strings"
            raise WorkflowConfigError(msg, path=dep_path)
        depends_on_list.append(dep_id)

    # 去重:保留首次出现的顺序,不得影响确定性与可测试性.
    seen: Set[str] = set()
    dedup: List[str] = []
    for dep_id in depends_on_list:
        if dep_id in seen:
            continue
        seen.add(dep_id)
        dedup.append(dep_id)
    return tuple(dedup)


def _parse_run_init_vars(init_vars_raw: object, *, item_path: str) -> Optional[Dict[str, object]]:
    msg: str
    if init_vars_raw is None:
        return None
    if not isinstance(init_vars_raw, dict):
        msg = "run.init_vars must be a mapping"
        raise WorkflowConfigError(msg, path="{}.init_vars".format(item_path))
    init_vars: Dict[str, object] = {}
    for key, value in cast("Dict[Any, Any]", init_vars_raw).items():
        if not isinstance(key, str) or not key.strip():
            msg = "run.init_vars keys must be non-empty strings"
            raise WorkflowConfigError(msg, path="{}.init_vars".format(item_path))
        init_vars[str(key)] = value
    return init_vars


def _normalize_write_intent_mapping(write_raw: object, *, write_path: str) -> Dict[str, object]:
    msg: str
    if not isinstance(write_raw, dict):
        msg = "write intent must be a mapping"
        raise WorkflowConfigError(msg, path=write_path)

    intent_mapping: Dict[str, object] = {}
    for raw_key, raw_value in cast("Dict[Any, Any]", write_raw).items():
        if not isinstance(raw_key, str) or not raw_key.strip():
            msg = "write intent keys must be non-empty strings"
            raise WorkflowConfigError(msg, path=write_path)
        intent_mapping[str(raw_key)] = raw_value
    return intent_mapping


def _parse_write_intent_cfg(kind: str, cfg_raw: object, *, write_path: str) -> Dict[str, object]:
    msg: str
    if not isinstance(cfg_raw, dict):
        msg = "run.writes.{} must be a mapping".format(kind)
        raise WorkflowConfigError(msg, path="{}.{}".format(write_path, kind))
    cfg_any = cast("Dict[Any, Any]", cfg_raw)
    cfg: Dict[str, object] = {}
    for cfg_key, cfg_value in cfg_any.items():
        if not isinstance(cfg_key, str) or not cfg_key.strip():
            msg = "run.writes.{} keys must be non-empty strings".format(kind)
            raise WorkflowConfigError(msg, path="{}.{}".format(write_path, kind))
        cfg[str(cfg_key)] = cfg_value
    return cfg


def _parse_write_intent_workbook_sheet(cfg: Mapping[str, object], *, write_path: str) -> WorkflowWriteToWorkbookSheet:
    msg: str
    workbook = str(cfg.get("workbook", "") or "").strip()
    sheet = str(cfg.get("sheet", "") or "").strip()
    output_id = str(cfg.get("output", "") or "").strip()
    on_conflict = str(cfg.get("on_conflict", "error") or "error").strip()
    if not workbook:
        msg = "run.writes.workbook_sheet.workbook must be a non-empty string"
        raise WorkflowConfigError(msg, path="{}.workbook_sheet.workbook".format(write_path))
    if not sheet:
        msg = "run.writes.workbook_sheet.sheet must be a non-empty string"
        raise WorkflowConfigError(msg, path="{}.workbook_sheet.sheet".format(write_path))
    if not output_id:
        msg = "run.writes.workbook_sheet.output must be a non-empty string"
        raise WorkflowConfigError(msg, path="{}.workbook_sheet.output".format(write_path))
    if on_conflict not in _WRITE_INTENT_ON_CONFLICT_POLICIES:
        msg = "run.writes.workbook_sheet.on_conflict must be one of: {}".format("/".join(_WRITE_INTENT_ON_CONFLICT_POLICIES))
        raise WorkflowConfigError(msg, path="{}.workbook_sheet.on_conflict".format(write_path))
    return WorkflowWriteToWorkbookSheet(
        workbook=workbook,
        sheet=sheet,
        output=output_id,
        on_conflict=on_conflict,
    )


def _parse_write_intent_workbook_append(cfg: Mapping[str, object], *, write_path: str) -> WorkflowWriteToWorkbookAppend:
    msg: str
    workbook = str(cfg.get("workbook", "") or "").strip()
    sheet = str(cfg.get("sheet", "") or "").strip()
    output_id = str(cfg.get("output", "") or "").strip()
    align_by = str(cfg.get("align_by", "field_id") or "field_id").strip()
    header_policy = str(cfg.get("header_policy", "once") or "once").strip()
    on_mismatch = str(cfg.get("on_mismatch", "error") or "error").strip()
    if not workbook:
        msg = "run.writes.workbook_append.workbook must be a non-empty string"
        raise WorkflowConfigError(msg, path="{}.workbook_append.workbook".format(write_path))
    if not sheet:
        msg = "run.writes.workbook_append.sheet must be a non-empty string"
        raise WorkflowConfigError(msg, path="{}.workbook_append.sheet".format(write_path))
    if not output_id:
        msg = "run.writes.workbook_append.output must be a non-empty string"
        raise WorkflowConfigError(msg, path="{}.workbook_append.output".format(write_path))
    if align_by not in _WRITE_INTENT_ALIGN_BY:
        msg = "run.writes.workbook_append.align_by must be one of: {}".format("/".join(_WRITE_INTENT_ALIGN_BY))
        raise WorkflowConfigError(msg, path="{}.workbook_append.align_by".format(write_path))
    if header_policy not in _WRITE_INTENT_HEADER_POLICIES:
        msg = "run.writes.workbook_append.header_policy must be one of: {}".format("/".join(_WRITE_INTENT_HEADER_POLICIES))
        raise WorkflowConfigError(msg, path="{}.workbook_append.header_policy".format(write_path))
    if on_mismatch not in _WRITE_INTENT_ON_MISMATCH_POLICIES:
        msg = "run.writes.workbook_append.on_mismatch must be one of: {}".format("/".join(_WRITE_INTENT_ON_MISMATCH_POLICIES))
        raise WorkflowConfigError(msg, path="{}.workbook_append.on_mismatch".format(write_path))
    return WorkflowWriteToWorkbookAppend(
        workbook=workbook,
        sheet=sheet,
        output=output_id,
        align_by=align_by,
        header_policy=header_policy,
        on_mismatch=on_mismatch,
    )


def _parse_write_intent_csv_append(cfg: Mapping[str, object], *, write_path: str) -> WorkflowWriteToCsvAppend:
    msg: str
    csv_id = str(cfg.get("csv", "") or "").strip()
    output_id = str(cfg.get("output", "") or "").strip()
    header_policy = str(cfg.get("header_policy", "once") or "once").strip()
    on_mismatch = str(cfg.get("on_mismatch", "error") or "error").strip()
    if not csv_id:
        msg = "run.writes.csv_append.csv must be a non-empty string"
        raise WorkflowConfigError(msg, path="{}.csv_append.csv".format(write_path))
    if not output_id:
        msg = "run.writes.csv_append.output must be a non-empty string"
        raise WorkflowConfigError(msg, path="{}.csv_append.output".format(write_path))
    if header_policy not in _WRITE_INTENT_HEADER_POLICIES:
        msg = "run.writes.csv_append.header_policy must be one of: {}".format("/".join(_WRITE_INTENT_HEADER_POLICIES))
        raise WorkflowConfigError(msg, path="{}.csv_append.header_policy".format(write_path))
    if on_mismatch not in _WRITE_INTENT_ON_MISMATCH_POLICIES:
        msg = "run.writes.csv_append.on_mismatch must be one of: {}".format("/".join(_WRITE_INTENT_ON_MISMATCH_POLICIES))
        raise WorkflowConfigError(msg, path="{}.csv_append.on_mismatch".format(write_path))
    return WorkflowWriteToCsvAppend(
        csv=csv_id,
        output=output_id,
        header_policy=header_policy,
        on_mismatch=on_mismatch,
    )


def _parse_write_intent_sheetbook_sheet(cfg: Mapping[str, object], *, write_path: str) -> WorkflowWriteToSheetbookSheet:
    msg: str
    sheetbook_id = str(cfg.get("sheetbook", "") or "").strip()
    sheet = str(cfg.get("sheet", "") or "").strip()
    output_id = str(cfg.get("output", "") or "").strip()
    on_conflict = str(cfg.get("on_conflict", "error") or "error").strip()
    if not sheetbook_id:
        msg = "run.writes.sheetbook_sheet.sheetbook must be a non-empty string"
        raise WorkflowConfigError(msg, path="{}.sheetbook_sheet.sheetbook".format(write_path))
    _validate_excel_sheet_name(sheet, path="{}.sheetbook_sheet.sheet".format(write_path))
    if not output_id:
        msg = "run.writes.sheetbook_sheet.output must be a non-empty string"
        raise WorkflowConfigError(msg, path="{}.sheetbook_sheet.output".format(write_path))
    if on_conflict not in _WRITE_INTENT_ON_CONFLICT_POLICIES:
        msg = "run.writes.sheetbook_sheet.on_conflict must be one of: {}".format("/".join(_WRITE_INTENT_ON_CONFLICT_POLICIES))
        raise WorkflowConfigError(msg, path="{}.sheetbook_sheet.on_conflict".format(write_path))
    return WorkflowWriteToSheetbookSheet(
        sheetbook=sheetbook_id,
        sheet=sheet,
        output=output_id,
        on_conflict=on_conflict,
    )


def _parse_write_intent_sheetbook_append(cfg: Mapping[str, object], *, write_path: str) -> WorkflowWriteToSheetbookAppend:
    msg: str
    sheetbook_id = str(cfg.get("sheetbook", "") or "").strip()
    sheet = str(cfg.get("sheet", "") or "").strip()
    output_id = str(cfg.get("output", "") or "").strip()
    align_by = str(cfg.get("align_by", "field_id") or "field_id").strip()
    header_policy = str(cfg.get("header_policy", "once") or "once").strip()
    on_mismatch = str(cfg.get("on_mismatch", "error") or "error").strip()
    if not sheetbook_id:
        msg = "run.writes.sheetbook_append.sheetbook must be a non-empty string"
        raise WorkflowConfigError(msg, path="{}.sheetbook_append.sheetbook".format(write_path))
    _validate_excel_sheet_name(sheet, path="{}.sheetbook_append.sheet".format(write_path))
    if not output_id:
        msg = "run.writes.sheetbook_append.output must be a non-empty string"
        raise WorkflowConfigError(msg, path="{}.sheetbook_append.output".format(write_path))
    if align_by not in _WRITE_INTENT_ALIGN_BY:
        msg = "run.writes.sheetbook_append.align_by must be one of: {}".format("/".join(_WRITE_INTENT_ALIGN_BY))
        raise WorkflowConfigError(msg, path="{}.sheetbook_append.align_by".format(write_path))
    if header_policy not in _WRITE_INTENT_HEADER_POLICIES:
        msg = "run.writes.sheetbook_append.header_policy must be one of: {}".format("/".join(_WRITE_INTENT_HEADER_POLICIES))
        raise WorkflowConfigError(msg, path="{}.sheetbook_append.header_policy".format(write_path))
    if on_mismatch not in _WRITE_INTENT_ON_MISMATCH_POLICIES:
        msg = "run.writes.sheetbook_append.on_mismatch must be one of: {}".format("/".join(_WRITE_INTENT_ON_MISMATCH_POLICIES))
        raise WorkflowConfigError(msg, path="{}.sheetbook_append.on_mismatch".format(write_path))
    return WorkflowWriteToSheetbookAppend(
        sheetbook=sheetbook_id,
        sheet=sheet,
        output=output_id,
        align_by=align_by,
        header_policy=header_policy,
        on_mismatch=on_mismatch,
    )


def _parse_write_intent(kind: str, cfg: Mapping[str, object], *, write_path: str) -> WorkflowWriteTo:
    if kind == "workbook_sheet":
        return _parse_write_intent_workbook_sheet(cfg, write_path=write_path)
    if kind == "workbook_append":
        return _parse_write_intent_workbook_append(cfg, write_path=write_path)
    if kind == "csv_append":
        return _parse_write_intent_csv_append(cfg, write_path=write_path)
    if kind == "sheetbook_sheet":
        return _parse_write_intent_sheetbook_sheet(cfg, write_path=write_path)
    if kind == "sheetbook_append":
        return _parse_write_intent_sheetbook_append(cfg, write_path=write_path)

    msg = "write intent contains unknown key: {}".format(kind)  # pragma: no cover
    raise WorkflowConfigError(msg, path=write_path)  # pragma: no cover


def _parse_run_writes(writes_raw: object, *, item_path: str) -> Tuple[WorkflowWriteTo, ...]:
    msg: str
    if writes_raw is None:
        return ()
    if not isinstance(writes_raw, list):
        msg = "run.writes must be a list of intents"
        raise WorkflowConfigError(msg, path="{}.writes".format(item_path))

    parsed: List[WorkflowWriteTo] = []
    for write_idx, write_raw in enumerate(cast("List[Any]", writes_raw)):
        write_path = "{}.writes.{}".format(item_path, int(write_idx))
        intent_mapping = _normalize_write_intent_mapping(write_raw, write_path=write_path)

        if len(intent_mapping) != 1:
            msg = "write intent must contain exactly one of: {}".format("/".join(_WRITE_INTENT_KEYS))
            raise WorkflowConfigError(msg, path=write_path)

        kind = next(iter(intent_mapping.keys()))
        if kind not in _WRITE_INTENT_KEYS:
            msg = "write intent contains unknown key: {}".format(kind)
            raise WorkflowConfigError(msg, path=write_path)

        cfg_raw = intent_mapping.get(kind)
        cfg = _parse_write_intent_cfg(str(kind), cfg_raw, write_path=write_path)
        parsed.append(_parse_write_intent(str(kind), cfg, write_path=write_path))

    return tuple(parsed)


def _load_workflow_runs(wf: Mapping[str, Any]) -> Tuple[List[WorkflowRun], Dict[str, int]]:
    msg: str
    runs_raw = wf.get("runs")
    if not isinstance(runs_raw, list) or not runs_raw:
        msg = "workflow.runs must be a non-empty list"
        raise WorkflowConfigError(msg, path="workflow.runs")

    seen_ids: Dict[str, int] = {}
    runs: List[WorkflowRun] = []
    for idx, item in enumerate(cast("List[Any]", runs_raw)):
        item_path = "workflow.runs.{}".format(idx)
        if not isinstance(item, dict):
            msg = "run entry must be a mapping"
            raise WorkflowConfigError(msg, path=item_path)
        run_dict = cast("Dict[str, Any]", item)
        run_id_raw = run_dict.get("id")
        demand_raw = run_dict.get("demand")
        if "deps" in run_dict:
            msg = "run.deps was removed; use run.depends_on"
            raise WorkflowConfigError(msg, path="{}.deps".format(item_path))
        if "write_to" in run_dict:
            msg = (
                "run.write_to was removed; use run.writes (list of intents). "
                "Migration: write_to: {<kind>: <cfg>} -> writes: [{<kind>: <cfg>}]"
            )
            raise WorkflowConfigError(msg, path="{}.write_to".format(item_path))

        run_id = str(run_id_raw or "").strip()
        if not run_id:
            msg = "run.id must be a non-empty string"
            raise WorkflowConfigError(msg, path="{}.id".format(item_path))
        if run_id.startswith(_INTERNAL_NODE_ID_PREFIX):
            msg = "run.id must not start with reserved prefix '{}'".format(_INTERNAL_NODE_ID_PREFIX)
            raise WorkflowConfigError(msg, path="{}.id".format(item_path))
        if run_id in seen_ids:
            msg = "Duplicate run.id '{}'".format(run_id)
            raise WorkflowConfigError(msg, path="{}.id".format(item_path))
        seen_ids[run_id] = idx

        demand = str(demand_raw or "").strip()
        if not demand:
            msg = "run.demand must be a non-empty string"
            raise WorkflowConfigError(msg, path="{}.demand".format(item_path))

        depends_on = _parse_run_depends_on(run_dict.get("depends_on"), item_path=item_path)
        init_vars = _parse_run_init_vars(run_dict.get("init_vars"), item_path=item_path)
        writes = _parse_run_writes(run_dict.get("writes"), item_path=item_path)
        runs.append(WorkflowRun(id=run_id, demand=demand, depends_on=depends_on, init_vars=init_vars, writes=writes))

    return runs, seen_ids


def _coerce_workflow_resources_mapping(wf: Mapping[str, Any]) -> Dict[str, Any]:
    msg: str
    resources_raw = wf.get("resources", {})
    if resources_raw is None:
        resources_raw = {}
    if not isinstance(resources_raw, dict):
        msg = "workflow.resources must be a mapping"
        raise WorkflowConfigError(msg, path="workflow.resources")
    resources_dict = cast("Dict[str, Any]", resources_raw)

    for raw_key in resources_dict:
        if not isinstance(raw_key, str) or not raw_key.strip():
            msg = "workflow.resources keys must be non-empty strings"
            raise WorkflowConfigError(msg, path="workflow.resources")

    unknown_resource_groups = sorted(k for k in resources_dict if str(k) not in _RESOURCE_GROUP_KEYS)
    if unknown_resource_groups:
        msg = "workflow.resources contains unknown keys: {}".format(",".join(str(k) for k in unknown_resource_groups))
        raise WorkflowConfigError(msg, path="workflow.resources")

    return resources_dict


def _coerce_workflow_resource_group_mapping(resources: Mapping[str, Any], *, group_key: str) -> Dict[str, Any]:
    msg: str
    raw = resources.get(str(group_key), {})
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        msg = "workflow.resources.{} must be a mapping".format(str(group_key))
        raise WorkflowConfigError(msg, path="workflow.resources.{}".format(str(group_key)))
    return cast("Dict[str, Any]", raw)


def _parse_workflow_workbook_resources(workbooks_raw: Mapping[str, Any]) -> Dict[str, WorkflowWorkbookResource]:
    msg: str
    workbooks: Dict[str, WorkflowWorkbookResource] = {}
    for raw_id, raw_cfg in cast("Dict[Any, Any]", workbooks_raw).items():
        resource_id = str(raw_id or "").strip() if isinstance(raw_id, str) else ""
        item_path = "workflow.resources.workbooks.{}".format(resource_id or "(invalid)")
        if not resource_id:
            msg = "workflow.resources.workbooks keys must be non-empty strings"
            raise WorkflowConfigError(msg, path="workflow.resources.workbooks")
        if not isinstance(raw_cfg, dict):
            msg = "workflow.resources.workbooks.<id> must be a mapping"
            raise WorkflowConfigError(msg, path=item_path)
        cfg = cast("Dict[str, Any]", raw_cfg)
        path_raw = cfg.get("path")
        path_text = str(path_raw or "").strip() if isinstance(path_raw, str) else ""
        if not path_text:
            msg = "workflow.resources.workbooks.<id>.path must be a non-empty string"
            raise WorkflowConfigError(msg, path="{}.path".format(item_path))
        allow_formulas_raw = cfg.get("allow_formulas", False)
        if not isinstance(allow_formulas_raw, bool):
            msg = "workflow.resources.workbooks.<id>.allow_formulas must be a bool"
            raise WorkflowConfigError(msg, path="{}.allow_formulas".format(item_path))
        workbooks[resource_id] = WorkflowWorkbookResource(path=path_text, allow_formulas=bool(allow_formulas_raw))
    return workbooks


def _parse_workflow_csv_resources(csvs_raw: Mapping[str, Any]) -> Dict[str, WorkflowCsvResource]:
    msg: str
    csvs: Dict[str, WorkflowCsvResource] = {}
    for raw_id, raw_cfg in cast("Dict[Any, Any]", csvs_raw).items():
        resource_id = str(raw_id or "").strip() if isinstance(raw_id, str) else ""
        item_path = "workflow.resources.csvs.{}".format(resource_id or "(invalid)")
        if not resource_id:
            msg = "workflow.resources.csvs keys must be non-empty strings"
            raise WorkflowConfigError(msg, path="workflow.resources.csvs")
        if not isinstance(raw_cfg, dict):
            msg = "workflow.resources.csvs.<id> must be a mapping"
            raise WorkflowConfigError(msg, path=item_path)
        cfg = cast("Dict[str, Any]", raw_cfg)
        path_raw = cfg.get("path")
        path_text = str(path_raw or "").strip() if isinstance(path_raw, str) else ""
        if not path_text:
            msg = "workflow.resources.csvs.<id>.path must be a non-empty string"
            raise WorkflowConfigError(msg, path="{}.path".format(item_path))
        csvs[resource_id] = WorkflowCsvResource(path=path_text)
    return csvs


def _parse_workflow_sheetbook_budget(budget_raw: object, *, item_path: str) -> WorkflowSheetbookBudget:
    msg: str
    if not isinstance(budget_raw, dict):
        msg = "workflow.resources.sheetbooks.<id>.budget must be a mapping"
        raise WorkflowConfigError(msg, path="{}.budget".format(item_path))
    budget_dict = cast("Dict[str, Any]", budget_raw)

    max_sheets_raw = budget_dict.get("max_sheets")
    max_total_cells_raw = budget_dict.get("max_total_cells")
    if isinstance(max_sheets_raw, bool) or not isinstance(max_sheets_raw, (int, float, str)):
        msg = "workflow.resources.sheetbooks.<id>.budget.max_sheets must be an integer >= 1"
        raise WorkflowConfigError(msg, path="{}.budget.max_sheets".format(item_path))
    if isinstance(max_total_cells_raw, bool) or not isinstance(max_total_cells_raw, (int, float, str)):
        msg = "workflow.resources.sheetbooks.<id>.budget.max_total_cells must be an integer >= 1"
        raise WorkflowConfigError(msg, path="{}.budget.max_total_cells".format(item_path))
    try:
        max_sheets = int(max_sheets_raw)
    except (TypeError, ValueError) as exc:
        msg = "workflow.resources.sheetbooks.<id>.budget.max_sheets must be an integer >= 1"
        raise WorkflowConfigError(msg, path="{}.budget.max_sheets".format(item_path)) from exc
    try:
        max_total_cells = int(max_total_cells_raw)
    except (TypeError, ValueError) as exc:
        msg = "workflow.resources.sheetbooks.<id>.budget.max_total_cells must be an integer >= 1"
        raise WorkflowConfigError(msg, path="{}.budget.max_total_cells".format(item_path)) from exc
    if max_sheets < 1:
        msg = "workflow.resources.sheetbooks.<id>.budget.max_sheets must be >= 1"
        raise WorkflowConfigError(msg, path="{}.budget.max_sheets".format(item_path))
    if max_total_cells < 1:
        msg = "workflow.resources.sheetbooks.<id>.budget.max_total_cells must be >= 1"
        raise WorkflowConfigError(msg, path="{}.budget.max_total_cells".format(item_path))

    return WorkflowSheetbookBudget(max_sheets=max_sheets, max_total_cells=max_total_cells)


def _parse_workflow_sheetbook_export_xlsx(export_raw: object, *, item_path: str) -> Optional[WorkflowSheetbookExportXlsx]:
    msg: str
    if export_raw is None:
        return None
    if not isinstance(export_raw, dict):
        msg = "workflow.resources.sheetbooks.<id>.export_xlsx must be a mapping"
        raise WorkflowConfigError(msg, path="{}.export_xlsx".format(item_path))
    export_dict = cast("Dict[str, Any]", export_raw)
    path_raw = export_dict.get("path")
    path_text = str(path_raw or "").strip() if isinstance(path_raw, str) else ""
    if not path_text:
        msg = "workflow.resources.sheetbooks.<id>.export_xlsx.path must be a non-empty string"
        raise WorkflowConfigError(msg, path="{}.export_xlsx.path".format(item_path))
    write_lock_raw = export_dict.get("write_lock", False)
    if not isinstance(write_lock_raw, bool):
        msg = "workflow.resources.sheetbooks.<id>.export_xlsx.write_lock must be a bool"
        raise WorkflowConfigError(msg, path="{}.export_xlsx.write_lock".format(item_path))
    allow_formulas_raw = export_dict.get("allow_formulas", False)
    if not isinstance(allow_formulas_raw, bool):
        msg = "workflow.resources.sheetbooks.<id>.export_xlsx.allow_formulas must be a bool"
        raise WorkflowConfigError(msg, path="{}.export_xlsx.allow_formulas".format(item_path))

    return WorkflowSheetbookExportXlsx(
        path=path_text,
        write_lock=bool(write_lock_raw),
        allow_formulas=bool(allow_formulas_raw),
    )


def _parse_workflow_sheetbook_resources(sheetbooks_raw: Mapping[str, Any]) -> Dict[str, WorkflowSheetbookResource]:
    msg: str
    sheetbooks: Dict[str, WorkflowSheetbookResource] = {}
    for raw_id, raw_cfg in cast("Dict[Any, Any]", sheetbooks_raw).items():
        resource_id = str(raw_id or "").strip() if isinstance(raw_id, str) else ""
        item_path = "workflow.resources.sheetbooks.{}".format(resource_id or "(invalid)")
        if not resource_id:
            msg = "workflow.resources.sheetbooks keys must be non-empty strings"
            raise WorkflowConfigError(msg, path="workflow.resources.sheetbooks")
        if not isinstance(raw_cfg, dict):
            msg = "workflow.resources.sheetbooks.<id> must be a mapping"
            raise WorkflowConfigError(msg, path=item_path)
        cfg = cast("Dict[str, Any]", raw_cfg)

        budget = _parse_workflow_sheetbook_budget(cfg.get("budget"), item_path=item_path)
        export_xlsx = _parse_workflow_sheetbook_export_xlsx(cfg.get("export_xlsx"), item_path=item_path)

        sheetbooks[resource_id] = WorkflowSheetbookResource(budget=budget, export_xlsx=export_xlsx)
    return sheetbooks


def _validate_workflow_resource_ids_unique(
    *,
    workbooks: Mapping[str, object],
    csvs: Mapping[str, object],
    sheetbooks: Mapping[str, object],
) -> None:
    msg: str
    overlap_workbooks_csvs = set(workbooks.keys()).intersection(set(csvs.keys()))
    overlap_workbooks_sheetbooks = set(workbooks.keys()).intersection(set(sheetbooks.keys()))
    overlap_csvs_sheetbooks = set(csvs.keys()).intersection(set(sheetbooks.keys()))
    overlap_all_set: Set[str] = set(overlap_workbooks_csvs).union(overlap_workbooks_sheetbooks, overlap_csvs_sheetbooks)
    overlap_all = sorted(overlap_all_set)
    if overlap_all:
        msg = "workflow.resources ids must be unique across workbooks/csvs/sheetbooks: {}".format(",".join(overlap_all))
        raise WorkflowConfigError(msg, path="workflow.resources")


def _load_workflow_resources(wf: Mapping[str, Any]) -> WorkflowResources:
    resources_dict = _coerce_workflow_resources_mapping(wf)

    workbooks_raw = _coerce_workflow_resource_group_mapping(resources_dict, group_key="workbooks")
    csvs_raw = _coerce_workflow_resource_group_mapping(resources_dict, group_key="csvs")
    sheetbooks_raw = _coerce_workflow_resource_group_mapping(resources_dict, group_key="sheetbooks")

    workbooks: Dict[str, WorkflowWorkbookResource] = {}
    workbooks = _parse_workflow_workbook_resources(workbooks_raw)

    csvs: Dict[str, WorkflowCsvResource] = {}
    csvs = _parse_workflow_csv_resources(csvs_raw)

    sheetbooks: Dict[str, WorkflowSheetbookResource] = {}
    sheetbooks = _parse_workflow_sheetbook_resources(sheetbooks_raw)

    _validate_workflow_resource_ids_unique(workbooks=workbooks, csvs=csvs, sheetbooks=sheetbooks)
    return WorkflowResources(workbooks=workbooks, csvs=csvs, sheetbooks=sheetbooks)


def _validate_workflow_run_writes_reference_resources(runs: Sequence[WorkflowRun], *, resources: WorkflowResources) -> None:
    msg: str

    kind_by_type = {
        WorkflowWriteToWorkbookSheet: "workbook_sheet",
        WorkflowWriteToWorkbookAppend: "workbook_append",
        WorkflowWriteToCsvAppend: "csv_append",
        WorkflowWriteToSheetbookSheet: "sheetbook_sheet",
        WorkflowWriteToSheetbookAppend: "sheetbook_append",
    }
    resource_ref_by_type = {
        WorkflowWriteToWorkbookSheet: ("workbooks", "workbook", "workbook"),
        WorkflowWriteToWorkbookAppend: ("workbooks", "workbook", "workbook"),
        WorkflowWriteToCsvAppend: ("csvs", "csv", "csv"),
        WorkflowWriteToSheetbookSheet: ("sheetbooks", "sheetbook", "sheetbook"),
        WorkflowWriteToSheetbookAppend: ("sheetbooks", "sheetbook", "sheetbook"),
    }
    resources_by_group = {
        "workbooks": resources.workbooks,
        "csvs": resources.csvs,
        "sheetbooks": resources.sheetbooks,
    }

    for idx, run in enumerate(runs):
        if not run.writes:
            continue
        item_path = "workflow.runs.{}".format(idx)
        for write_idx, intent in enumerate(run.writes):
            kind = kind_by_type.get(type(intent), "unknown")
            ref = resource_ref_by_type.get(type(intent))
            if ref is None:
                continue  # pragma: no cover
            group_key, attr_name, resource_label = ref
            resource_id = str(getattr(intent, attr_name, "") or "")
            if resource_id not in resources_by_group[group_key]:
                msg = "Unknown {} resource id: run_id={!r}, intent_kind={!r}, resource_id={!r}, output_id={!r}".format(
                    str(resource_label),
                    str(run.id),
                    kind,
                    resource_id,
                    str(getattr(intent, "output", "") or ""),
                )
                raise WorkflowConfigError(msg, path="{}.writes.{}.{}.{}".format(item_path, int(write_idx), kind, attr_name))


def _load_workflow_ctx_options(ctx_raw: object) -> WorkflowCtxOptions:
    msg: str
    ctx = WorkflowCtxOptions()
    if ctx_raw is None:
        return ctx
    if not isinstance(ctx_raw, dict):
        msg = "workflow.options.ctx must be a mapping"
        raise WorkflowConfigError(msg, path="workflow.options.ctx")
    ctx_dict = cast("Dict[str, Any]", ctx_raw)

    max_value_bytes_raw = ctx_dict.get("max_value_bytes", 65536)
    if isinstance(max_value_bytes_raw, bool) or not isinstance(max_value_bytes_raw, (int, float, str)):
        msg = "workflow.options.ctx.max_value_bytes must be an integer >= 1"
        raise WorkflowConfigError(msg, path="workflow.options.ctx.max_value_bytes")
    try:
        max_value_bytes = int(max_value_bytes_raw)
    except (TypeError, ValueError) as exc:
        msg = "workflow.options.ctx.max_value_bytes must be an integer >= 1"
        raise WorkflowConfigError(msg, path="workflow.options.ctx.max_value_bytes") from exc
    if max_value_bytes < 1:
        msg = "workflow.options.ctx.max_value_bytes must be >= 1"
        raise WorkflowConfigError(msg, path="workflow.options.ctx.max_value_bytes")

    max_bytes_raw = ctx_dict.get("max_bytes", 1048576)
    if isinstance(max_bytes_raw, bool) or not isinstance(max_bytes_raw, (int, float, str)):
        msg = "workflow.options.ctx.max_bytes must be an integer >= 1"
        raise WorkflowConfigError(msg, path="workflow.options.ctx.max_bytes")
    try:
        max_bytes = int(max_bytes_raw)
    except (TypeError, ValueError) as exc:
        msg = "workflow.options.ctx.max_bytes must be an integer >= 1"
        raise WorkflowConfigError(msg, path="workflow.options.ctx.max_bytes") from exc
    if max_bytes < 1:
        msg = "workflow.options.ctx.max_bytes must be >= 1"
        raise WorkflowConfigError(msg, path="workflow.options.ctx.max_bytes")

    return WorkflowCtxOptions(
        max_value_bytes=max_value_bytes,
        max_bytes=max_bytes,
    )


def _parse_workflow_cache_pool_budget(budget_raw: object) -> "WorkflowCachePoolBudget":
    msg: str
    if not isinstance(budget_raw, dict):
        msg = "workflow.options.cache_pool.budget must be a mapping"
        raise WorkflowConfigError(msg, path="workflow.options.cache_pool.budget")
    budget_dict = cast("Dict[str, Any]", budget_raw)

    max_entries_raw = budget_dict.get("max_entries")
    if isinstance(max_entries_raw, bool) or not isinstance(max_entries_raw, (int, float, str)):
        msg = "workflow.options.cache_pool.budget.max_entries must be an integer >= 1"
        raise WorkflowConfigError(msg, path="workflow.options.cache_pool.budget.max_entries")
    try:
        max_entries = int(max_entries_raw)
    except (TypeError, ValueError) as exc:
        msg = "workflow.options.cache_pool.budget.max_entries must be an integer >= 1"
        raise WorkflowConfigError(msg, path="workflow.options.cache_pool.budget.max_entries") from exc
    if max_entries < 1:
        msg = "workflow.options.cache_pool.budget.max_entries must be >= 1"
        raise WorkflowConfigError(msg, path="workflow.options.cache_pool.budget.max_entries")

    over_budget_policy = str(budget_dict.get("over_budget_policy", "") or "").strip()
    if over_budget_policy not in _CACHE_POOL_OVER_BUDGET_POLICIES:
        msg = "workflow.options.cache_pool.budget.over_budget_policy must be one of: {}".format("/".join(_CACHE_POOL_OVER_BUDGET_POLICIES))
        raise WorkflowConfigError(msg, path="workflow.options.cache_pool.budget.over_budget_policy")

    return WorkflowCachePoolBudget(
        max_entries=max_entries,
        over_budget_policy=over_budget_policy,
    )


def _parse_workflow_cache_pool_pins(pin_raw: object) -> Tuple["WorkflowCachePoolPin", ...]:
    msg: str
    if pin_raw is None:
        pin_raw = []
    if not isinstance(pin_raw, list):
        msg = "workflow.options.cache_pool.pin must be a list of mappings"
        raise WorkflowConfigError(msg, path="workflow.options.cache_pool.pin")
    pins: List[WorkflowCachePoolPin] = []
    for idx, item in enumerate(cast("List[Any]", pin_raw)):
        pin_path = "workflow.options.cache_pool.pin.{}".format(idx)
        if not isinstance(item, dict):
            msg = "workflow.options.cache_pool.pin items must be mappings"
            raise WorkflowConfigError(msg, path=pin_path)
        pin_dict = cast("Dict[str, Any]", item)
        kind = str(pin_dict.get("kind", "") or "").strip()
        if kind not in _CACHE_POOL_PIN_KINDS:
            msg = "workflow.options.cache_pool.pin[*].kind must be one of: {}".format("/".join(_CACHE_POOL_PIN_KINDS))
            raise WorkflowConfigError(msg, path="{}.kind".format(pin_path))
        source_id = str(pin_dict.get("source_id", "") or "").strip()
        if not source_id:
            msg = "workflow.options.cache_pool.pin[*].source_id must be a non-empty string"
            raise WorkflowConfigError(msg, path="{}.source_id".format(pin_path))
        pins.append(WorkflowCachePoolPin(kind=kind, source_id=source_id))
    return tuple(pins)


def _load_workflow_cache_pool_options(cache_pool_raw: object) -> Optional["WorkflowCachePoolOptions"]:
    msg: str
    if cache_pool_raw is None:
        return None
    if not isinstance(cache_pool_raw, dict):
        msg = "workflow.options.cache_pool must be a mapping"
        raise WorkflowConfigError(msg, path="workflow.options.cache_pool")
    cache_pool_dict = cast("Dict[str, Any]", cache_pool_raw)

    conflict_policy = str(cache_pool_dict.get("conflict_policy", "") or "").strip()
    if conflict_policy not in _CACHE_POOL_CONFLICT_POLICIES:
        msg = "workflow.options.cache_pool.conflict_policy must be one of: {}".format("/".join(_CACHE_POOL_CONFLICT_POLICIES))
        raise WorkflowConfigError(msg, path="workflow.options.cache_pool.conflict_policy")

    release_policy = str(cache_pool_dict.get("release_policy", "") or "").strip()
    if release_policy not in _CACHE_POOL_RELEASE_POLICIES:
        msg = "workflow.options.cache_pool.release_policy must be one of: {}".format("/".join(_CACHE_POOL_RELEASE_POLICIES))
        raise WorkflowConfigError(msg, path="workflow.options.cache_pool.release_policy")

    budget = _parse_workflow_cache_pool_budget(cache_pool_dict.get("budget"))
    pins = _parse_workflow_cache_pool_pins(cache_pool_dict.get("pin"))
    return WorkflowCachePoolOptions(
        conflict_policy=conflict_policy,
        release_policy=release_policy,
        budget=budget,
        pin=pins,
    )


def _load_workflow_options(wf: Mapping[str, Any]) -> WorkflowOptions:
    msg: str
    options_raw = wf.get("options", {})
    if options_raw is None:
        options_raw = {}
    if not isinstance(options_raw, dict):
        msg = "workflow.options must be a mapping"
        raise WorkflowConfigError(msg, path="workflow.options")
    options_dict = cast("Dict[str, Any]", options_raw)

    max_concurrency_raw = options_dict.get("max_concurrency", 1)
    if isinstance(max_concurrency_raw, bool) or not isinstance(max_concurrency_raw, (int, float, str)):
        msg = "workflow.options.max_concurrency must be an integer >= 1"
        raise WorkflowConfigError(msg, path="workflow.options.max_concurrency")
    try:
        max_concurrency = int(max_concurrency_raw)
    except (TypeError, ValueError) as exc:
        msg = "workflow.options.max_concurrency must be an integer >= 1"
        raise WorkflowConfigError(msg, path="workflow.options.max_concurrency") from exc
    if max_concurrency < 1:
        msg = "workflow.options.max_concurrency must be >= 1"
        raise WorkflowConfigError(msg, path="workflow.options.max_concurrency")

    failure_policy = str(options_dict.get("failure_policy", "all_fail") or "all_fail").strip()
    if failure_policy not in _FAILURE_POLICIES:
        msg = "workflow.options.failure_policy must be one of: {}".format("/".join(_FAILURE_POLICIES))
        raise WorkflowConfigError(msg, path="workflow.options.failure_policy")

    ctx = _load_workflow_ctx_options(options_dict.get("ctx"))

    if "share_preload_cache" in options_dict:
        msg = "workflow.options.share_preload_cache was removed; use workflow.options.cache_pool"
        raise WorkflowConfigError(msg, path="workflow.options.share_preload_cache")

    cache_pool = _load_workflow_cache_pool_options(options_dict.get("cache_pool"))

    return WorkflowOptions(
        max_concurrency=max_concurrency,
        failure_policy=failure_policy,
        cache_pool=cache_pool,
        ctx=ctx,
    )


def load_workflow_config_from_mapping(root: Dict[str, Any]) -> WorkflowConfig:
    """从已解析的 `mapping` 加载 `workflow` 配置(用于文本校验/编辑器等无文件系统场景)."""
    msg: str
    wf_raw = root.get("workflow")
    if not isinstance(wf_raw, dict):
        msg = "Missing required mapping 'workflow'"
        raise WorkflowConfigError(msg, path="workflow")
    wf = cast("Dict[str, Any]", wf_raw)

    runs, seen_ids = _load_workflow_runs(wf)
    _validate_workflow_deps(runs, seen_ids=seen_ids)
    resources = _load_workflow_resources(wf)
    _validate_workflow_run_writes_reference_resources(runs, resources=resources)
    options = _load_workflow_options(wf)

    return WorkflowConfig(
        runs=tuple(runs),
        options=options,
        resources=resources,
    )


def _validate_workflow_deps(
    runs: Sequence[WorkflowRun],
    *,
    seen_ids: Mapping[str, int],
) -> None:
    _validate_workflow_deps_references(runs, seen_ids=seen_ids)
    _validate_workflow_deps_no_cycles(runs, seen_ids=seen_ids)


def _validate_workflow_deps_references(
    runs: Sequence[WorkflowRun],
    *,
    seen_ids: Mapping[str, int],
) -> None:
    msg: str
    run_ids = set(seen_ids.keys())
    for idx, run in enumerate(runs):
        item_path = "workflow.runs.{}".format(idx)
        for dep_id in run.depends_on:
            if dep_id == run.id:
                msg = "run.depends_on must not include self dependency: '{}'".format(dep_id)
                raise WorkflowConfigError(msg, path="{}.depends_on".format(item_path))
            if dep_id not in run_ids:
                msg = "Unknown run.depends_on id '{}'".format(dep_id)
                raise WorkflowConfigError(msg, path="{}.depends_on".format(item_path))


def _validate_workflow_deps_no_cycles(  # noqa: C901
    runs: Sequence[WorkflowRun],
    *,
    seen_ids: Mapping[str, int],
) -> None:
    msg: str
    by_id: Dict[str, WorkflowRun] = {run.id: run for run in runs}
    ordered_ids = sorted(by_id.keys(), key=lambda rid: int(seen_ids.get(rid, 0)))

    visiting: Set[str] = set()
    visited: Set[str] = set()
    stack: List[str] = []

    def dfs(node_id: str) -> Optional[List[str]]:
        visiting.add(node_id)
        stack.append(node_id)
        run = by_id[node_id]
        for dep_id in run.depends_on:
            if dep_id not in by_id:
                continue  # pragma: no cover
            if dep_id in visited:
                continue
            if dep_id in visiting:
                if dep_id in stack:
                    idx = stack.index(dep_id)
                    return [*stack[idx:], dep_id]
                return [dep_id, node_id, dep_id]  # pragma: no cover
            found = dfs(dep_id)
            if found is not None:
                return found

        visiting.remove(node_id)
        visited.add(node_id)
        _ = stack.pop()
        return None

    for node_id in ordered_ids:
        if node_id in visited:
            continue
        found = dfs(node_id)
        if found is not None:
            msg = "workflow depends_on must not contain cycles (cycle_path={})".format(json.dumps(found, ensure_ascii=False))
            raise WorkflowConfigError(msg, path="workflow.runs[*].depends_on")


__all__ = [
    "WorkflowCachePoolBudget",
    "WorkflowCachePoolOptions",
    "WorkflowCachePoolPin",
    "WorkflowConfig",
    "WorkflowConfigError",
    "WorkflowOptions",
    "WorkflowResources",
    "WorkflowRun",
    "WorkflowWriteTo",
    "WorkflowWriteToCsvAppend",
    "WorkflowWriteToSheetbookAppend",
    "WorkflowWriteToSheetbookSheet",
    "WorkflowWriteToWorkbookAppend",
    "WorkflowWriteToWorkbookSheet",
    "load_workflow_config",
    "load_workflow_config_from_mapping",
    "resolve_workflow_demand_path",
    "validate_workflow_yaml_text_json",
]
