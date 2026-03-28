import importlib
from pathlib import Path
from typing import Dict, FrozenSet, Iterable, Iterator, List, Mapping, Sequence, Tuple

import pytest


_CURATED_PUBLIC_MODULES: Tuple[str, ...] = (
    "scalim.dsl.by_yaml",
    "scalim.dsl.by_yaml.tools",
    "scalim.dsl.by_yaml.workflow",
    "scalim.dsl.by_yaml.workflow_types",
    "scalim.dsl.by_yaml.workflow_paths",
    "scalim.spec.ir",
    "scalim.workflow.loaders",
    "scalim.events",
    "scalim.sinks",
)


_EXPECTED_PUBLIC_ALL: Mapping[str, FrozenSet[str]] = {
    "scalim.dsl.by_yaml": frozenset(
        [
            "UNSET",
            "Compilation",
            "ResolverTrustedMode",
            "RunOverrides",
            "RunResult",
            "compile",
            "run",
            "run_workflow",
        ]
    ),
    "scalim.dsl.by_yaml.tools": frozenset(["OutputConfigDict", "derive_base_module_path", "load_output_config"]),
    "scalim.dsl.by_yaml.workflow": frozenset(
        [
            "WorkflowCachePoolBudget",
            "WorkflowCachePoolOptions",
            "WorkflowCachePoolPin",
            "WorkflowConfig",
            "ScalimWorkflowConfigError",
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
    ),
    "scalim.dsl.by_yaml.workflow_types": frozenset(
        [
            "WorkflowCachePoolBudget",
            "WorkflowCachePoolOptions",
            "WorkflowCachePoolPin",
            "WorkflowConfig",
            "ScalimWorkflowConfigError",
            "WorkflowOptions",
            "WorkflowResources",
            "WorkflowRun",
            "WorkflowWriteTo",
            "WorkflowWriteToCsvAppend",
            "WorkflowWriteToSheetbookAppend",
            "WorkflowWriteToSheetbookSheet",
            "WorkflowWriteToWorkbookAppend",
            "WorkflowWriteToWorkbookSheet",
        ]
    ),
    "scalim.dsl.by_yaml.workflow_paths": frozenset(["resolve_workflow_demand_path"]),
    "scalim.spec.ir": frozenset(
        [
            "BindingIr",
            "ComputeCallContextIr",
            "CsvFieldPresentationIr",
            "DemandIr",
            "DerivedFieldIr",
            "ExportProfileIr",
            "FieldIr",
            "FieldPresentationIr",
            "FieldRefIr",
            "JoinConditionIr",
            "KeyIr",
            "LoaderCallContextIr",
            "LoaderExtractor",
            "LoaderIr",
            "LoaderParamsBuilder",
            "LoaderResultMapCallable",
            "LookupKeyCast",
            "LookupKeySpec",
            "LookupStepIr",
            "MainSourceIr",
            "MainSourceRowIterableCallable",
            "NormalizedLookupKeySpec",
            "OrderByKeyIr",
            "PandasFieldPresentationIr",
            "RelationIr",
            "SourceIr",
            "SourceNormalizeIr",
            "SourceRefIr",
            "SpreadsheetFieldPresentationIr",
            "SupportedFieldIr",
            "build_stable_lookup_key_list",
        ]
    ),
    "scalim.workflow.loaders": frozenset(["sheetbook_sheet_rows", "workflow_loader_context"]),
    "scalim.events": frozenset(
        [
            "EVENT_ADAPTIVE_SCHEDULER_DECISION",
            "EVENT_BATCH_END",
            "EVENT_BATCH_START",
            "EVENT_COLUMN_WRITE",
            "EVENT_DIAGNOSTIC_WARNING",
            "EVENT_ERROR",
            "EVENT_FIELD_COMPUTE",
            "EVENT_FIELD_SLIM",
            "EVENT_LOADER_CALL",
            "EVENT_LOADER_RETRY",
            "EVENT_LOADER_SLIM",
            "EVENT_OUTPUT_TARGET_END",
            "EVENT_PIPELINE_END",
            "EVENT_PIPELINE_START",
            "EVENT_RELATION_LOOKUP",
            "EVENT_ROW_RELEASE",
            "EVENT_ROW_WRITE",
            "EVENT_STAGE_SPAN",
            "EVENT_WORKFLOW_CACHE_ACQUIRE",
            "EVENT_WORKFLOW_CACHE_EVICT",
            "EVENT_WORKFLOW_CACHE_RELEASE",
            "EVENT_WORKFLOW_NODE_CANCELLED",
            "EVENT_WORKFLOW_NODE_END",
            "EVENT_WORKFLOW_NODE_START",
            "EVENT_WORKFLOW_RESOURCE_COMMIT",
            "EVENT_WORKFLOW_RESOURCE_CREATE",
            "EVENT_WORKFLOW_RESOURCE_DISCARD",
            "EVENT_WORKFLOW_RESOURCE_WRITE",
            "WORKFLOW_ATTRIBUTION_META_KEYS",
            "WORKFLOW_EVENT_PREFIX_CACHE",
            "WORKFLOW_EVENT_PREFIX_NODE",
            "WORKFLOW_EVENT_PREFIX_RESOURCE",
            "WORKFLOW_EVENT_PREFIXES",
            "WORKFLOW_EXEC_ID_META_KEY",
            "WORKFLOW_NODE_CANCELLED_REASON_DEPENDENCY_FAILED",
            "WORKFLOW_NODE_CANCELLED_REASON_POLICY_ALL_FAIL",
            "WORKFLOW_NODE_CANCELLED_REASON_UPSTREAM_CANCELLED",
            "WORKFLOW_NODE_END_STATUS_ERROR",
            "WORKFLOW_NODE_END_STATUS_OK",
            "WORKFLOW_NODE_ID_META_KEY",
            "Event",
            "EventDescriptor",
            "generate_run_id",
            "get_event_catalog",
            "get_event_catalog_map",
            "now_ts",
        ]
    ),
    "scalim.sinks": frozenset(
        [
            "BaseColumnSink",
            "BaseRowSink",
            "BaseSink",
            "BlockColumnCSVSink",
            "CSVSink",
            "ColumnBatch",
            "ColumnCSVSink",
            "ColumnData",
            "ColumnExcelSink",
            "ColumnValues",
            "ExcelSink",
            "ExcelWorkbookSink",
            "IColumnSink",
            "IRowSink",
            "ISink",
            "InMemoryColumnSink",
            "InMemoryCsv",
            "InMemoryCsvSink",
            "InMemoryListSink",
            "InMemoryRowSink",
            "PandasColumnSink",
            "PandasRowSink",
        ]
    ),
}


def test_curated_public_modules_import_smoke() -> None:
    for module_name in _CURATED_PUBLIC_MODULES:
        _ = importlib.import_module(module_name)


def test_curated_public_modules_use_explicit_all_whitelists() -> None:
    missing: Dict[str, Sequence[str]] = {}
    stale: Dict[str, Sequence[str]] = {}
    for module_name, expected in _EXPECTED_PUBLIC_ALL.items():
        mod = importlib.import_module(module_name)
        declared = tuple(getattr(mod, "__all__", ()))
        declared_set = frozenset(str(x) for x in declared)

        missing_names = tuple(sorted(expected - declared_set))
        stale_names = tuple(sorted(declared_set - expected))
        if missing_names:
            missing[module_name] = missing_names
        if stale_names:
            stale[module_name] = stale_names

    assert not missing, "curated module __all__ missing names:\n{}".format(missing)
    assert not stale, "curated module __all__ contains stale names:\n{}".format(stale)


def test_by_yaml_tools_smoke() -> None:
    from scalim.dsl.by_yaml.tools import derive_base_module_path, load_output_config

    repo_root = _repo_root()
    yaml_path = str(repo_root / "tests" / "fixtures" / "order_report.yaml")

    cfg = load_output_config(yaml_path)
    assert isinstance(cfg, dict)
    for required_key in ("params", "field_name_mapping", "output_fields", "outputs"):
        assert required_key in cfg

    base_module_path = derive_base_module_path(yaml_path, sys_path=[str(repo_root)], cwd=str(repo_root))
    assert base_module_path == "tests.fixtures"


def test_public_template_sandbox_rejects_unknown_values() -> None:
    from scalim.dsl.by_yaml._public_template_sandbox import validate_public_template_sandbox

    with pytest.raises(ValueError, match="template_sandbox"):
        _ = validate_public_template_sandbox("nope")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _iter_text_files(roots: Iterable[Path], *, suffixes: Tuple[str, ...]) -> Iterator[Path]:
    for root in roots:
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if "__pycache__" in p.parts:
                continue
            if p.suffix not in suffixes:
                continue
            yield p


def _find_banned_lines(text: str, *, banned: Tuple[str, ...]) -> List[Tuple[int, str]]:
    hits: List[Tuple[int, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for token in banned:
            if token in line:
                hits.append((lineno, token))
    return hits


def test_user_visible_materials_must_not_promote_internal_module_paths() -> None:
    repo_root = _repo_root()
    banned = (
        "scalim.dsl.by_yaml.runtime.",
        "scalim.dsl.by_yaml.config_parsing.",
        "scalim.dsl.by_yaml.schema_dsl.",
        "scalim.events._",
        "scalim.sinks._internal.",
    )
    roots = (
        repo_root / "docs" / "doc",
        repo_root / "notebooks" / "marimo",
        repo_root / "artifacts" / "skills",
    )

    violations: List[str] = []
    for p in _iter_text_files(roots, suffixes=(".md", ".py")):
        text = p.read_text(encoding="utf-8")
        for lineno, token in _find_banned_lines(text, banned=banned):
            rel = p.relative_to(repo_root).as_posix()
            violations.append("{}:{}: {}".format(rel, lineno, token))

    assert not violations, "internal module paths must not appear in user-visible materials:\n{}".format("\n".join(violations))
