# pragma: allow-c901-file plan: c75
"""`workflow` 编译: `demand YAML` 预加载 + `outputs` 写入节点注入.

职责:
- 预加载 `demand YAML` (`YamlDemandLoader.load`) 并返回 `DemandConfig` 映射.
- 计算有效 `outputs` (覆盖项/默认绑定), 并将写入节点注入 `workflow DAG`.

边界:
- 本模块包含 `filesystem IO` (见 `_load_demands`).
- 本模块不负责 `resources` 编译 (`books/files` 资源 `IR`) 与 `runtime options` 解析.
"""

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from ....spec.ir._workflow import (
    AppendSheetNodeIr,
    WorkflowAnyNodeIr,
    WorkflowEdgeIr,
    WorkflowNodeIr,
    WorkflowNodeType,
    WriteSheetNodeIr,
)
from ....vendor.dataclassesx import replace
from ..book_resource_policy import ResourcesPolicy, resolve_write_defaults_config
from ..runtime.contracts import OutputOverride, RunOverrides
from ..schema_dsl.models import BookConfig, BookWriteDefaultsConfig, DemandConfig, FileConfig, OutputTargetConfig
from ..schema_dsl.output_enums import (
    DEFAULT_BOOK_WRITE_ALIGN_BY,
    DEFAULT_BOOK_WRITE_HEADER_POLICY,
    DEFAULT_BOOK_WRITE_MODE,
    DEFAULT_BOOK_WRITE_ON_CONFLICT,
    DEFAULT_BOOK_WRITE_ON_MISMATCH,
)
from ..workflow import ScalimWorkflowConfigError, WorkflowConfig
from . import resource_override as _resource_override_ssot
from .book_identity import is_pathful_book
from .config_parsing.loader import YamlDemandLoader
from .validation_contracts import validate_excel_sheet_name as _validate_excel_sheet_name_ssot

__all__ = ()

_INTERNAL_NODE_ID_PREFIX = "__wf__"


def _validate_excel_sheet_name(sheet: str, *, path: str) -> None:
    _validate_excel_sheet_name_ssot(str(sheet), path=str(path))


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


def _effective_write_defaults(
    book_id: str,
    *,
    resources_policy: Optional[ResourcesPolicy] = None,
) -> BookWriteDefaultsConfig:
    policy = resources_policy if isinstance(resources_policy, ResourcesPolicy) else None
    return resolve_write_defaults_config(book_id=str(book_id), resources_policy=policy)


def _validate_xlsx_memory_align_by(
    *,
    book: BookConfig,
    book_id: str,
    effective_defaults: BookWriteDefaultsConfig,
) -> None:
    if is_pathful_book(book):
        return

    if str(effective_defaults.mode or DEFAULT_BOOK_WRITE_MODE) != "append":
        return
    if str(effective_defaults.align_by or "") != "header":
        return

    align_by_path = "resources_policy.books.{}.write.align_by".format(str(book_id))
    msg = (
        "pathless books (in-memory bus) do not support BookWritePolicy.align_by=header; "
        "internal rows only use canonical field keys. Migrate to BookWriteAlignBy.FIELD_ID "
        "and keep write.header_fields_output_by for export display (book_id={!r})"
    ).format(str(book_id))
    raise ScalimWorkflowConfigError(msg, path=str(align_by_path))


def _load_demands(
    demand_yaml_paths_by_run_id: Mapping[str, str],
    *,
    template_vars: Optional[Mapping[str, Any]],
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


def _apply_overrides_output_extras(
    demand_cfg_by_run_id: Dict[str, DemandConfig], *, overrides: Optional[RunOverrides]
) -> Dict[str, DemandConfig]:
    if overrides is None or overrides.output_extras is None:
        return demand_cfg_by_run_id
    meta, audit = _resource_override_ssot.compile_output_extras_override(overrides.output_extras, path="overrides.output_extras")

    next_cfg: Dict[str, DemandConfig] = {}
    for run_id, cfg in demand_cfg_by_run_id.items():
        next_cfg[str(run_id)] = replace(cfg, meta=meta, audit=audit)
    return next_cfg


def _parse_overrides_outputs_defaults_book_id(defaults: Optional[Any]) -> Optional[str]:
    return _resource_override_ssot.parse_outputs_defaults_book_id(defaults, path="overrides.outputs_defaults")


def _apply_default_book_binding_to_outputs(
    outputs: Tuple[OutputTargetConfig, ...],
    *,
    default_book_id: str,
) -> Tuple[OutputTargetConfig, ...]:
    return _resource_override_ssot.apply_default_book_binding_to_outputs(outputs, default_book_id=str(default_book_id))


def _effective_outputs_for_workflow_compile(
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
    return _resource_override_ssot.parse_overrides_outputs_targets(
        overrides_outputs,
        path="overrides.outputs",
        default_book_id=default_book_id,
        default_book_ref="overrides.outputs_defaults.to.book",
        known_field_ids=None,
    )


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
    write_defaults: Any,
    write_defaults_mode_path: str,
) -> WorkflowAnyNodeIr:
    effective_defaults = write_defaults

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
    resources_policy: Optional[ResourcesPolicy] = None,
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
                effective_defaults=_effective_write_defaults(str(book_id), resources_policy=resources_policy),
            )

            sheet_name, sheet_ref_path = _effective_sheet_name_for_output(out_cfg, idx=int(out_idx), outputs_path=outputs_path)
            try:
                _validate_excel_sheet_name(sheet_name, path=str(sheet_ref_path))
            except ValueError as exc:
                raise ScalimWorkflowConfigError(str(exc), path=str(sheet_ref_path)) from exc

            base_defaults = _effective_write_defaults(str(book_id), resources_policy=resources_policy)
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
                write_defaults_mode_path="resources_policy.books.{}.write.mode".format(str(book_id)),
            )

            nodes.append(node)
            for dep_id in write_deps:
                edges.append(WorkflowEdgeIr(from_node_id=str(dep_id), to_node_id=str(node_id)))

            if not is_pathful_book(book):
                xlsx_memory_write_node_ids_by_run_id.setdefault(str(run.id), []).append(str(node_id))

        # `meta`/`audit` 额外工作表: 在工作流模式下通过推导的写入节点写出.
        extras: List[Tuple[str, Any, str]] = []
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

            base_defaults = _effective_write_defaults(str(default_book_id), resources_policy=resources_policy)
            effective_defaults = base_defaults
            mode = str(effective_defaults.mode or DEFAULT_BOOK_WRITE_MODE)
            _validate_xlsx_memory_align_by(
                book=book,
                book_id=str(default_book_id),
                effective_defaults=effective_defaults,
            )

            for extra_id, extra_cfg_obj, default_sheet in extras:
                extra_cfg = extra_cfg_obj
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
                    write_defaults_mode_path="resources_policy.books.{}.write.mode".format(str(default_book_id)),
                )

                nodes.append(node)
                for dep_id in write_deps:
                    edges.append(WorkflowEdgeIr(from_node_id=str(dep_id), to_node_id=str(node_id)))

                if not is_pathful_book(book):
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


def validate_excel_sheet_name(sheet: str, *, path: str) -> None:
    _validate_excel_sheet_name(sheet, path=path)


def outputs_path_ref(outputs_path: str, idx: int, suffix: str) -> str:
    return _outputs_path_ref(outputs_path, idx, suffix)


def effective_book_binding_for_output(
    out_cfg: OutputTargetConfig,
    *,
    idx: int,
    outputs_path: str,
) -> Tuple[Optional[str], str]:
    return _effective_book_binding_for_output(out_cfg, idx=idx, outputs_path=outputs_path)


def effective_file_binding_for_output(
    out_cfg: OutputTargetConfig,
    *,
    idx: int,
    outputs_path: str,
) -> Tuple[Optional[str], str]:
    return _effective_file_binding_for_output(out_cfg, idx=idx, outputs_path=outputs_path)


def effective_sheet_name_for_output(out_cfg: OutputTargetConfig, *, idx: int, outputs_path: str) -> Tuple[str, str]:
    return _effective_sheet_name_for_output(out_cfg, idx=idx, outputs_path=outputs_path)


def effective_write_defaults(
    book_id: str,
    *,
    resources_policy: Optional[ResourcesPolicy] = None,
) -> BookWriteDefaultsConfig:
    return _effective_write_defaults(str(book_id), resources_policy=resources_policy)


def validate_xlsx_memory_align_by(
    *,
    book: BookConfig,
    book_id: str,
    effective_defaults: Optional[BookWriteDefaultsConfig] = None,
    resources_policy: Optional[ResourcesPolicy] = None,
) -> None:
    defaults = effective_defaults
    if defaults is None:
        defaults = _effective_write_defaults(str(book_id), resources_policy=resources_policy)
    _validate_xlsx_memory_align_by(book=book, book_id=book_id, effective_defaults=defaults)


def load_demands(
    demand_yaml_paths_by_run_id: Mapping[str, str],
    *,
    template_vars: Optional[Mapping[str, Any]],
    template_sandbox: str,
    rendered_yaml_max_len: int,
    allowed_yaml_roots: Optional[Tuple[str, ...]],
) -> Dict[str, DemandConfig]:
    return _load_demands(
        demand_yaml_paths_by_run_id,
        template_vars=template_vars,
        template_sandbox=template_sandbox,
        rendered_yaml_max_len=rendered_yaml_max_len,
        allowed_yaml_roots=allowed_yaml_roots,
    )


def apply_overrides_output_extras(
    demand_cfg_by_run_id: Dict[str, DemandConfig], *, overrides: Optional[RunOverrides]
) -> Dict[str, DemandConfig]:
    return _apply_overrides_output_extras(demand_cfg_by_run_id, overrides=overrides)


def parse_overrides_outputs_defaults_book_id(defaults: Optional[Any]) -> Optional[str]:
    return _parse_overrides_outputs_defaults_book_id(defaults)


def apply_default_book_binding_to_outputs(
    outputs: Tuple[OutputTargetConfig, ...],
    *,
    default_book_id: str,
) -> Tuple[OutputTargetConfig, ...]:
    return _apply_default_book_binding_to_outputs(outputs, default_book_id=default_book_id)


def effective_outputs_for_workflow_compile(
    config: DemandConfig,
    *,
    overrides_outputs: Optional[Sequence[OutputOverride]],
    default_book_id: Optional[str],
) -> Tuple[OutputTargetConfig, ...]:
    return _effective_outputs_for_workflow_compile(
        config,
        overrides_outputs=overrides_outputs,
        default_book_id=default_book_id,
    )


def build_write_node_for_book(
    *,
    node_id: str,
    decl_order: int,
    deps: Sequence[str],
    book_id: str,
    sheet_name: str,
    input_node_id: str,
    input_output_id: str,
    mode: str,
    write_defaults: Any,
    write_defaults_mode_path: str,
) -> WorkflowAnyNodeIr:
    return _build_write_node_for_book(
        node_id=node_id,
        decl_order=decl_order,
        deps=deps,
        book_id=book_id,
        sheet_name=sheet_name,
        input_node_id=input_node_id,
        input_output_id=input_output_id,
        mode=mode,
        write_defaults=write_defaults,
        write_defaults_mode_path=write_defaults_mode_path,
    )


def append_write_nodes_from_runs(
    wf_obj: WorkflowConfig,
    *,
    demand_cfg_by_run_id: Mapping[str, DemandConfig],
    nodes: List[WorkflowAnyNodeIr],
    edges: List[WorkflowEdgeIr],
    effective_books: Mapping[str, BookConfig],
    effective_files: Mapping[str, FileConfig],
    overrides_outputs: Optional[Sequence[OutputOverride]],
    default_book_id: Optional[str],
    resources_policy: Optional[ResourcesPolicy] = None,
) -> Dict[str, List[str]]:
    return _append_write_nodes_from_runs(
        wf_obj,
        demand_cfg_by_run_id=demand_cfg_by_run_id,
        nodes=nodes,
        edges=edges,
        effective_books=effective_books,
        effective_files=effective_files,
        overrides_outputs=overrides_outputs,
        default_book_id=default_book_id,
        resources_policy=resources_policy,
    )


def inject_xlsx_memory_write_dependencies(
    xlsx_memory_write_node_ids_by_run_id: Mapping[str, List[str]],
    direct_dependents_by_run_id: Mapping[str, List[str]],
    demand_node_pos_by_run_id: Mapping[str, int],
    nodes: List[WorkflowAnyNodeIr],
    edges: List[WorkflowEdgeIr],
) -> None:
    _inject_xlsx_memory_write_dependencies(
        xlsx_memory_write_node_ids_by_run_id,
        direct_dependents_by_run_id,
        demand_node_pos_by_run_id,
        nodes,
        edges,
    )
