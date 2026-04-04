"""`workflow` 预检查(`preflight`)(内部模块).

目标:
- 在 `workflow` 引擎启动前运行一组“运行期但可推理”的诊断
- 快速失败:发现第一个错误立即抛出,并中止整个 `workflow`

约束:
- 运行时需兼容 `Python 3.6`
- 必须基于每个 `run` 的有效运行期策略/覆盖项(由调用侧准备好 `RunOptions`)进行判断
"""

from typing import Dict, List, Optional, Sequence, Tuple

from ...vendor.compact.typing_extensionsx import Protocol
from ...vendor.dataclassesx import dataclass, replace
from ._internal.config_parsing.loader import YamlDemandLoader
from .diagnostics import format_duplicate_effective_field_display_names_message
from .runtime.contracts import OutputOverride, ResourcesOverride, RunOptions
from .schema_dsl.constants import DEFAULT_OUTPUT_HEADER_BY, DEFAULT_OUTPUT_INCLUDE_HEADER
from .schema_dsl.models import DemandConfig, OutputTargetConfig, OutputToConfig
from .schema_dsl.output_enums import DEFAULT_BOOK_WRITE_HEADER_POLICY, DEFAULT_BOOK_WRITE_MODE
from .workflow import ScalimWorkflowConfigError


@dataclass(frozen=True)
class WorkflowPreflightContext:
    workflow_yaml_path: str


@dataclass(frozen=True)
class WorkflowPreflightRun:
    run_id: str
    demand_path: str
    decl_order: int
    options: RunOptions


class WorkflowPreflightCheck(Protocol):
    check_id: str

    def run(self, ctx: WorkflowPreflightContext, run: WorkflowPreflightRun) -> None: ...


def run_workflow_preflight(
    ctx: WorkflowPreflightContext,
    *,
    runs: Sequence[WorkflowPreflightRun],
    checks: Sequence[WorkflowPreflightCheck],
) -> None:
    ordered = sorted(runs, key=lambda r: int(r.decl_order))
    for run in ordered:
        for check in checks:
            check.run(ctx, run)


def _apply_default_book_binding_to_outputs(
    outputs: Tuple[OutputTargetConfig, ...],
    *,
    default_book_id: str,
) -> Tuple[OutputTargetConfig, ...]:
    if not outputs:
        return outputs
    if not default_book_id:
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


def _effective_book_write_mode(
    config: DemandConfig,
    *,
    resources_override: Optional[ResourcesOverride],
    book_id: str,
) -> str:
    mode = str(DEFAULT_BOOK_WRITE_MODE)

    book_cfg = None
    if config.resources is not None:
        book_cfg = config.resources.books.get(str(book_id))
    if book_cfg is not None and book_cfg.write_defaults is not None:
        raw_text = str(book_cfg.write_defaults.mode or "").strip()
        if raw_text:
            mode = raw_text

    if resources_override is not None and resources_override.books is not None:
        book_override = resources_override.books.get(str(book_id))
        if book_override is not None and book_override.write_defaults is not None:
            raw_text = str(book_override.write_defaults.mode or "").strip()
            if raw_text:
                mode = raw_text

    return mode


def _effective_book_header_policy(
    config: DemandConfig,
    *,
    resources_override: Optional[ResourcesOverride],
    book_id: str,
) -> str:
    header_policy = str(DEFAULT_BOOK_WRITE_HEADER_POLICY)

    book_cfg = None
    if config.resources is not None:
        book_cfg = config.resources.books.get(str(book_id))
    if book_cfg is not None and book_cfg.write_defaults is not None:
        raw_text = str(book_cfg.write_defaults.header_policy or "").strip()
        if raw_text:
            header_policy = raw_text

    if resources_override is not None and resources_override.books is not None:
        book_override = resources_override.books.get(str(book_id))
        if book_override is not None and book_override.write_defaults is not None:
            raw_text = str(book_override.write_defaults.header_policy or "").strip()
            if raw_text:
                header_policy = raw_text

    return header_policy


def _output_target_requires_unique_effective_field_display_names(
    config: DemandConfig,
    output: OutputTargetConfig,
    *,
    resources_override: Optional[ResourcesOverride],
) -> bool:
    to_cfg = output.to
    if to_cfg is None:
        return False

    write_cfg = output.write
    header_by = str(DEFAULT_OUTPUT_HEADER_BY)
    if write_cfg is not None and write_cfg.header_fields_output_by is not None:
        header_by = str(write_cfg.header_fields_output_by)
    if header_by != "name":
        return False

    file_id = str(to_cfg.file or "").strip() if to_cfg.file is not None else ""
    if file_id:
        include_header = DEFAULT_OUTPUT_INCLUDE_HEADER
        if write_cfg is not None and write_cfg.include_header is not None:
            include_header = bool(write_cfg.include_header)
        return bool(include_header)

    book_id = str(to_cfg.book or "").strip() if to_cfg.book is not None else ""
    if not book_id:
        return False

    mode = _effective_book_write_mode(config, resources_override=resources_override, book_id=str(book_id))
    header_policy = _effective_book_header_policy(config, resources_override=resources_override, book_id=str(book_id))

    if str(mode).strip() == "append":
        return header_policy != "never"

    include_header = DEFAULT_OUTPUT_INCLUDE_HEADER
    if write_cfg is not None and write_cfg.include_header is not None:
        include_header = bool(write_cfg.include_header)
    return bool(include_header)


def _output_override_requires_unique_effective_field_display_names(
    config: DemandConfig,
    output: OutputOverride,
    *,
    default_book_id: Optional[str],
    resources_override: Optional[ResourcesOverride],
) -> bool:
    to_cfg = output.to
    write_cfg = output.write

    header_by = str(DEFAULT_OUTPUT_HEADER_BY)
    if write_cfg is not None and write_cfg.header_fields_output_by is not None:
        header_by = str(write_cfg.header_fields_output_by)
    if header_by != "name":
        return False

    file_id = str(to_cfg.file or "").strip() if to_cfg.file is not None else ""
    if file_id:
        include_header = DEFAULT_OUTPUT_INCLUDE_HEADER
        if write_cfg is not None and write_cfg.include_header is not None:
            include_header = bool(write_cfg.include_header)
        return bool(include_header)

    book_id = str(to_cfg.book or "").strip() if to_cfg.book is not None else ""
    if not book_id and default_book_id:
        book_id = str(default_book_id)
    if not book_id:
        return False

    mode = _effective_book_write_mode(config, resources_override=resources_override, book_id=str(book_id))
    header_policy = _effective_book_header_policy(config, resources_override=resources_override, book_id=str(book_id))

    if str(mode).strip() == "append":
        return header_policy != "never"

    include_header = DEFAULT_OUTPUT_INCLUDE_HEADER
    if write_cfg is not None and write_cfg.include_header is not None:
        include_header = bool(write_cfg.include_header)
    return bool(include_header)


def _effective_outputs_require_unique_effective_field_display_names(
    config: DemandConfig,
    *,
    options: RunOptions,
) -> bool:
    overrides = options.overrides
    outputs_override = None if overrides is None else overrides.outputs
    defaults = None if overrides is None else overrides.outputs_defaults
    resources_override = None if overrides is None else overrides.resources

    default_book_id = None
    if defaults is not None:
        default_book_id = str(defaults.to.book or "").strip() or None

    if outputs_override is not None:
        for out_override in outputs_override:
            if _output_override_requires_unique_effective_field_display_names(
                config,
                out_override,
                default_book_id=default_book_id,
                resources_override=resources_override,
            ):
                return True
        return False

    outputs = tuple(config.outputs)
    if default_book_id is not None:
        outputs = _apply_default_book_binding_to_outputs(outputs, default_book_id=str(default_book_id))
    for out_cfg in outputs:
        if _output_target_requires_unique_effective_field_display_names(config, out_cfg, resources_override=resources_override):
            return True
    return False


def _collect_duplicate_effective_field_display_names(config: DemandConfig) -> Dict[str, List[str]]:
    conflicts: Dict[str, List[str]] = {}

    for field_id, field_cfg in config.source_fields.items():
        name = str(field_cfg.name or "").strip()
        effective = name or str(field_id)
        conflicts.setdefault(effective, []).append(str(field_id))

    for field_id, field_cfg in config.derived_fields.items():
        name = str(field_cfg.name or "").strip()
        effective = name or str(field_id)
        conflicts.setdefault(effective, []).append(str(field_id))

    return {name: ids for name, ids in conflicts.items() if len(ids) > 1}


class ValidateUniqueFieldNamesPreflightCheck:
    check_id: str = "validate_unique_field_names"

    def run(self, ctx: WorkflowPreflightContext, run: WorkflowPreflightRun) -> None:
        _ = ctx

        demand_diagnostics = run.options.demand_diagnostics
        validate_unique = True if demand_diagnostics is None else bool(demand_diagnostics.validate_unique_field_names)
        if not validate_unique:
            return

        loader = YamlDemandLoader()
        config = loader.load(
            str(run.demand_path),
            template_vars=run.options.template_vars,
            template_sandbox=run.options.template_sandbox,
            rendered_yaml_max_len=run.options.rendered_yaml_max_len,
            allowed_yaml_roots=run.options.allowed_yaml_roots,
            # `preflight` 必须按有效的 `outputs/overrides` 口径判断是否触发;
            # 这里禁止让 YAML 层校验器先按原始 YAML `outputs` 抢跑该检查.
            validate_unique_field_names=False,
        )

        if not _effective_outputs_require_unique_effective_field_display_names(config, options=run.options):
            return

        duplicates = _collect_duplicate_effective_field_display_names(config)
        if not duplicates:
            return

        msg = format_duplicate_effective_field_display_names_message(duplicates)
        full = "Workflow preflight failed: run_id={!r}, demand_path={!r}: {}".format(str(run.run_id), str(run.demand_path), msg)
        path = "workflow.runs.{}.demand".format(int(run.decl_order))
        raise ScalimWorkflowConfigError(full, path=path)


WORKFLOW_PREFLIGHT_CHECKS: Tuple[WorkflowPreflightCheck, ...] = (ValidateUniqueFieldNamesPreflightCheck(),)


__all__ = (
    "WORKFLOW_PREFLIGHT_CHECKS",
    "WorkflowPreflightCheck",
    "WorkflowPreflightContext",
    "WorkflowPreflightRun",
    "run_workflow_preflight",
)
