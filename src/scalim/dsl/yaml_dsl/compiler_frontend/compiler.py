from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from ....planning import PlanBuilder
from ....planning.snapshots import execution_deps_snapshot, execution_plan_snapshot
from .._internal.config_parsing.error_envelope import ErrorEnvelope, ErrorLoc, ScalimYamlValidationError
from .._internal.config_parsing.imports import ScalimYamlImportExpansionError, contains_import_syntax, expand_imports_inplace
from .._internal.config_parsing.loader import YamlDemandLoader
from .._internal.config_parsing.models import RawDemand
from .._internal.config_parsing.validator import ConfigValidator
from .._internal.config_parsing.yaml_load import envelope_from_validation_issue, error_loc_for_yaml_path, load_yaml_mapping_text
from ..runtime.conversion import ConfigToIRConverter
from .contracts import FrontendDiagnostics, StaticCompilation


def _iter_file_import_cache_paths(cache: Dict[str, Dict[str, Any]]) -> List[str]:
    files: List[str] = []
    for key in sorted(cache.keys()):
        if not key:
            continue
        if key.startswith("scalim://"):
            continue
        p = Path(str(key)).expanduser().resolve(strict=False)
        if not p.exists() or not p.is_file():
            continue
        files.append(str(p))
    return files


def _load_yaml_mapping_with_locations(
    yaml_text: str,
    *,
    yaml_path: Path,
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Tuple[int, int]], FrontendDiagnostics]:
    try:
        yaml_data, locations, _lines = load_yaml_mapping_text(
            str(yaml_text or ""),
            source_path=str(yaml_path),
            detect_duplicate_keys=True,
        )
    except ScalimYamlValidationError as exc:
        return None, {}, FrontendDiagnostics(errors=exc.errors, warnings=exc.warnings)
    except Exception as exc:  # noqa: BLE001
        env = ErrorEnvelope(
            code="yaml_parse_failed",
            message="YAML parse failed: {}: {}".format(type(exc).__name__, exc),
            source_path=str(yaml_path),
            path="(root)",
            loc=ErrorLoc(1, 1),
        )
        return None, {}, FrontendDiagnostics(errors=(env,), warnings=())
    return yaml_data, locations, FrontendDiagnostics()


def _validate_demand_yaml(
    yaml_data: Dict[str, Any],
    *,
    yaml_path: Path,
    locations: Dict[str, Tuple[int, int]],
) -> FrontendDiagnostics:
    report = ConfigValidator().validate_report(
        yaml_data,
        strict_unknown_fields=True,
        enable_jsonschema_validation=True,
    )

    errors: List[ErrorEnvelope] = []
    warnings: List[ErrorEnvelope] = []

    for issue in report.errors():
        errors.append(
            envelope_from_validation_issue(
                issue,
                source_path=str(yaml_path),
                locations=locations,
                default_code="yaml_validate_error",
            )
        )

    for issue in report.warnings():
        warnings.append(
            envelope_from_validation_issue(
                issue,
                source_path=str(yaml_path),
                locations=locations,
                default_code="yaml_validate_warning",
            )
        )

    return FrontendDiagnostics(errors=tuple(errors), warnings=tuple(warnings))


def compile_demand_frontend_diagnostics(
    yaml_path: Union[str, Path],
    *,
    yaml_text: Optional[str] = None,
    allowed_yaml_roots: Optional[Sequence[Union[str, Path]]] = None,
    scalim_yaml_override: Optional[Union[str, Path]] = None,
    project_root_override: Optional[Union[str, Path]] = None,
) -> StaticCompilation:
    """编译单个需求 YAML,产出诊断信息与生效后的 YAML 视图(不导入/不执行用户模块).

    说明:
    - 该入口不要求白名单(`allowlist`).
    - `imports` 展开阶段会从磁盘读取片段;当提供 `yaml_text` 时,入口文件优先使用该文本.
    - 任何失败都应降级为诊断信息(不应出现未捕获异常导致的崩溃).
    """

    yaml_path_resolved = Path(str(yaml_path)).expanduser().resolve(strict=False)
    if yaml_text is None:
        try:
            yaml_text = yaml_path_resolved.read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            env = ErrorEnvelope(
                code="yaml_read_failed",
                message="Failed to read YAML file: {}: {}".format(type(exc).__name__, exc),
                source_path=str(yaml_path_resolved),
                path="(file)",
                loc=ErrorLoc(1, 1),
            )
            return StaticCompilation(diagnostics=FrontendDiagnostics(errors=(env,), warnings=()))

    yaml_data, locations, parse_diags = _load_yaml_mapping_with_locations(yaml_text, yaml_path=yaml_path_resolved)
    if yaml_data is None:
        return StaticCompilation(diagnostics=parse_diags)

    import_cache: Dict[str, Dict[str, Any]] = {}
    fragment_files: Tuple[str, ...] = ()
    if contains_import_syntax(yaml_data):
        try:
            _ = expand_imports_inplace(
                yaml_data,
                yaml_path=yaml_path_resolved,
                cache=import_cache,
                allowed_yaml_roots=allowed_yaml_roots,
                scalim_yaml_override=scalim_yaml_override,
                project_root_override=project_root_override,
            )
            fragment_files = tuple(_iter_file_import_cache_paths(import_cache))
        except ScalimYamlImportExpansionError as exc:
            logical_path = str(exc.logical_path or "(root)")
            env = ErrorEnvelope(
                code="yaml_import_expansion_error",
                message=str(exc),
                source_path=str(yaml_path_resolved),
                path=logical_path,
                loc=error_loc_for_yaml_path(logical_path, locations),
            )
            return StaticCompilation(
                diagnostics=FrontendDiagnostics(errors=(env,), warnings=()),
                effective_yaml=yaml_data,
                import_fragment_files=(),
            )
        except Exception as exc:  # noqa: BLE001
            env = ErrorEnvelope(
                code="yaml_import_expansion_error",
                message="imports expansion failed unexpectedly: {}: {}".format(type(exc).__name__, exc),
                source_path=str(yaml_path_resolved),
                path="(imports)",
                loc=ErrorLoc(1, 1),
            )
            return StaticCompilation(
                diagnostics=FrontendDiagnostics(errors=(env,), warnings=()),
                effective_yaml=yaml_data,
                import_fragment_files=(),
            )

    diags = _validate_demand_yaml(yaml_data, yaml_path=yaml_path_resolved, locations=locations)
    if not diags.ok():
        return StaticCompilation(
            diagnostics=diags,
            effective_yaml=yaml_data,
            import_fragment_files=fragment_files,
        )

    return StaticCompilation(
        diagnostics=diags,
        effective_yaml=yaml_data,
        import_fragment_files=fragment_files,
    )


def compile_demand_frontend(
    yaml_path: Union[str, Path],
    *,
    yaml_text: Optional[str] = None,
    allowed_yaml_roots: Optional[Sequence[Union[str, Path]]] = None,
    scalim_yaml_override: Optional[Union[str, Path]] = None,
    project_root_override: Optional[Union[str, Path]] = None,
) -> StaticCompilation:
    """编译单个需求 YAML,产出静态 IR 与 `ExecutionPlan`(不导入/不执行用户模块)."""

    base = compile_demand_frontend_diagnostics(
        yaml_path,
        yaml_text=yaml_text,
        allowed_yaml_roots=allowed_yaml_roots,
        scalim_yaml_override=scalim_yaml_override,
        project_root_override=project_root_override,
    )
    if not base.diagnostics.ok():
        return base

    try:
        raw_demand = RawDemand.from_raw(base.effective_yaml or {})
        demand_config = YamlDemandLoader().parse_raw_demand(raw_demand)
    except ScalimYamlValidationError as exc:
        return StaticCompilation(
            diagnostics=FrontendDiagnostics(errors=exc.errors, warnings=exc.warnings),
            effective_yaml=base.effective_yaml,
            import_fragment_files=base.import_fragment_files,
        )
    except Exception as exc:  # noqa: BLE001
        env = ErrorEnvelope(
            code="yaml_frontend_config_error",
            message="Failed to parse demand config: {}: {}".format(type(exc).__name__, exc),
            source_path=str(yaml_path),
            path="(root)",
            loc=ErrorLoc(1, 1),
        )
        return StaticCompilation(
            diagnostics=FrontendDiagnostics(errors=(env,), warnings=()),
            effective_yaml=base.effective_yaml,
            import_fragment_files=base.import_fragment_files,
        )

    try:
        demand_ir = ConfigToIRConverter(init_vars=None).convert(demand_config)
    except Exception as exc:  # noqa: BLE001
        env = ErrorEnvelope(
            code="yaml_frontend_ir_error",
            message="Failed to build static IR: {}: {}".format(type(exc).__name__, exc),
            source_path=str(yaml_path),
            path="(ir)",
            loc=ErrorLoc(1, 1),
        )
        return StaticCompilation(
            diagnostics=FrontendDiagnostics(errors=(env,), warnings=()),
            effective_yaml=base.effective_yaml,
            import_fragment_files=base.import_fragment_files,
        )

    try:
        plan = PlanBuilder(demand_ir).build(targets=None)
        plan_snap = execution_plan_snapshot(plan)
        deps_snap = execution_deps_snapshot(plan)
    except Exception as exc:  # noqa: BLE001
        env = ErrorEnvelope(
            code="yaml_frontend_plan_error",
            message="Failed to build ExecutionPlan: {}: {}".format(type(exc).__name__, exc),
            source_path=str(yaml_path),
            path="(plan)",
            loc=ErrorLoc(1, 1),
        )
        return StaticCompilation(
            diagnostics=FrontendDiagnostics(errors=(env,), warnings=()),
            effective_yaml=base.effective_yaml,
            import_fragment_files=base.import_fragment_files,
            demand_ir=demand_ir,
        )

    return StaticCompilation(
        diagnostics=base.diagnostics,
        effective_yaml=base.effective_yaml,
        import_fragment_files=base.import_fragment_files,
        demand_ir=demand_ir,
        plan=plan,
        plan_snapshot=plan_snap,
        deps_snapshot=deps_snap,
    )


__all__ = (
    "compile_demand_frontend",
    "compile_demand_frontend_diagnostics",
)
