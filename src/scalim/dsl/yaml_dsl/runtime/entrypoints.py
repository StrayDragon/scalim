# pragma: allow-c901-file plan: c10
import logging
from pathlib import Path
from typing import Dict, Optional

from ....execution.run_ir import run_ir
from ....execution.versioned_outputs import (
    ensure_output_root_layout,
    ensure_version_dir,
    parse_versioned_output_path,
    update_latest,
    version_manifest_relpath,
    write_version_manifest,
)
from ....hooks.policy_signals import PreUseBatchSizeDecision, emit_pre_use_batch_size_signal
from ....ob.components import split_components
from ....vendor.dataclassesx import replace
from .compiler import compile as _compile
from .contracts import Compilation, RunOptions, RunResult, UnsetType
from .normalize import normalize_public_run_options

_policy_logger = logging.getLogger("scalim.dsl.yaml_dsl.runtime.policy")


def _ensure_versioned_output_dirs(compilation: Compilation) -> None:  # noqa: C901
    spec = compilation.request.output_composition
    if spec is None:
        return

    roots: Dict[str, str] = {}

    def _collect(path_str: Optional[str]) -> None:
        if not path_str:
            return
        p = Path(str(path_str))
        if "versions" not in p.parts:
            return
        parsed = parse_versioned_output_path(p)
        root_str = str(parsed.root)
        version_id = str(parsed.version_id)
        existing = roots.get(root_str)
        if existing is None:
            roots[root_str] = version_id
            return
        if existing != version_id:
            msg = "Multiple version_id values for the same output root: root={!r}, version_id={!r} vs {!r}".format(
                root_str, existing, version_id
            )
            raise ValueError(msg)

    for t in spec.targets:
        _collect(t.output.path)
    for t in spec.derived_targets:
        _collect(t.output.path)
    if spec.meta_sheet is not None:
        _collect(spec.meta_sheet.output.path)
    if spec.audit_sheet is not None:
        _collect(spec.audit_sheet.output.path)

    for root_str, version_id in roots.items():
        layout = ensure_output_root_layout(Path(root_str))
        _ = ensure_version_dir(layout, version_id=str(version_id))


def _update_versioned_output_manifests(result: "RunResult") -> None:
    outputs = result.core.outputs or {}
    if not outputs:
        return

    books_by_root: Dict[str, Dict[str, str]] = {}
    files_by_root: Dict[str, Dict[str, str]] = {}
    version_id_by_root: Dict[str, str] = {}

    for output_path in outputs.values():
        if not output_path:
            continue
        p = Path(str(output_path))
        if "versions" not in p.parts:
            continue
        parsed = parse_versioned_output_path(p)
        root_str = str(parsed.root)
        version_id = str(parsed.version_id)
        existing = version_id_by_root.get(root_str)
        if existing is None:
            version_id_by_root[root_str] = version_id
        elif existing != version_id:
            msg = "Multiple version_id values for the same output root: root={!r}, version_id={!r} vs {!r}".format(
                root_str, existing, version_id
            )
            raise ValueError(msg)
        if parsed.kind == "books":
            books_by_root.setdefault(root_str, {})[str(parsed.artifact_id)] = str(parsed.artifact_relpath)
        else:
            files_by_root.setdefault(root_str, {})[str(parsed.artifact_id)] = str(parsed.artifact_relpath)

    for root_str, version_id in version_id_by_root.items():
        layout = ensure_output_root_layout(Path(root_str))
        _ = write_version_manifest(
            layout,
            version_id=str(version_id),
            books=books_by_root.get(root_str) or {},
            files=files_by_root.get(root_str) or {},
        )
        _ = update_latest(
            layout,
            version_id=str(version_id),
            version_manifest_relpath=version_manifest_relpath(version_id=str(version_id)),
        )


def run(
    yaml_path: str,
    *,
    options: RunOptions,
) -> RunResult:
    """运行 `YAML DSL` 官方入口.

    优先级(高 -> 低):
    - `options.overrides.outputs`(完全覆盖 `YAML` 的 `outputs`; 整体替换,即 `replace`; 非空)
    - `YAML` 的 `outputs`(若声明)
    - 执行默认值

    注意:
    - YAML 主线不再支持 `observability.*`(旧字段会发出迁移告警并被忽略);可观测性通过 `components=[Observer()/Hook()]` 与
      `RunOptions(components=[...], overrides=RunOverrides(viz_config=VizObserverConfig(...)))` 装配.
    - `options.overrides.viz_config` 可启用/禁用 `viz` 并控制落盘路径、`trace` 输出与 `payload_policy` 策略等.
    - 当 `options.overrides.outputs` 把 `YAML` 中的 `workbook` 输出整体替换为非 `workbook` 输出时,未显式设置 `path` 的 `meta/audit`
      会被跳过;若仍需保留,请为 `meta.path` / `audit.path` 提供独立 `workbook` 路径.
    - 输出数据的保留完全由 `options.sink`(例如 `InMemoryRowSink`)决定,而不是由布尔开关控制.
    """
    options = normalize_public_run_options(options)
    compilation = _compile(yaml_path, options=options)
    _ensure_versioned_output_dirs(compilation)

    request = compilation.request
    if isinstance(options.batch_size, UnsetType):
        _observers, hooks = split_components(request.components)
        runtime_bindings = request.runtime_bindings
        main_source_id = compilation.demand_ir.main_source.source_id
        main_loader = None if runtime_bindings is None else runtime_bindings.main_source_loaders.get(str(main_source_id))
        decision = PreUseBatchSizeDecision(
            value=request.batch_size,
            demand_path=str(yaml_path),
            init_vars=options.init_vars,
            main_loader=main_loader,
        )
        emit_pre_use_batch_size_signal(hooks, decision)
        request = replace(request, batch_size=decision.value)

        if decision.history:
            _policy_logger.info("`pre_use_batch_size` 决策完成: 批大小=%s 改写轨迹=%s", decision.value, decision.history)
        else:
            _policy_logger.debug("`pre_use_batch_size` 决策完成: 批大小=%s 改写轨迹=%s", decision.value, decision.history)

    core = run_ir(compilation.demand_ir, request)
    result = RunResult(core, config=compilation.config, yaml_path=yaml_path, sink=options.sink)
    _update_versioned_output_manifests(result)
    return result


def compile(  # noqa: A001
    yaml_path: str,
    *,
    options: RunOptions,
) -> Compilation:
    options = normalize_public_run_options(options)
    return _compile(yaml_path, options=options)


__all__ = (
    "compile",
    "run",
)
