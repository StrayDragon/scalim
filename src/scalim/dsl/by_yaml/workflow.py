import heapq
import json
import re
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional, Sequence, Tuple, cast

from ...vendor.compact.importlibx import require_optional_dependency

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


class WorkflowConfigError(ValueError):
    path: str

    def __init__(self, message: str, *, path: str = "") -> None:
        self.path = str(path or "")
        super(WorkflowConfigError, self).__init__(self._format(message))

    def _format(self, message: str) -> str:
        if not self.path:
            return str(message)
        return "{} (path={})".format(message, self.path)


@dataclass(frozen=True)
class WorkflowRun:
    id: str
    demand: str
    deps: Tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkflowOptions:
    max_concurrency: int = 1
    failure_policy: str = "all_fail"
    cache_pool: Optional["WorkflowCachePoolOptions"] = None


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
    resources: Dict[str, object] = dataclass_field(default_factory=dict)


def load_workflow_config(workflow_yaml_path: str) -> WorkflowConfig:
    yaml_path = Path(str(workflow_yaml_path or "")).expanduser()
    try:
        text = yaml_path.read_text(encoding="utf-8")
    except Exception as exc:
        msg = "Failed to read workflow YAML: {}: {}".format(type(exc).__name__, exc)
        raise WorkflowConfigError(msg, path="(file)") from exc

    try:
        loaded = yaml.safe_load(text)
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
) -> Path:
    raw = str(demand or "").strip()
    if not raw:
        msg = "run.demand must be a non-empty string"
        raise WorkflowConfigError(msg, path="workflow.runs[*].demand")

    wf_path = Path(str(workflow_yaml_path or "")).expanduser().resolve(strict=False)
    base_dir = wf_path.parent

    if raw.startswith("@/"):
        alias = "@"
        rel = raw[2:]
        return _resolve_alias_path(
            alias=alias,
            rel=rel,
            raw=raw,
            path_aliases=path_aliases,
            run_id=run_id,
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
        )

    p = Path(raw).expanduser()
    if p.is_absolute():
        return p.resolve(strict=False)

    return (base_dir / p).resolve(strict=False)


def _resolve_alias_path(
    *,
    alias: str,
    rel: str,
    raw: str,
    path_aliases: Optional[Mapping[str, str]],
    run_id: Optional[str],
) -> Path:
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
    return (base / rel_path).resolve(strict=False)


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
        yaml_data = yaml.safe_load(yaml_text)
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


def load_workflow_config_from_mapping(root: Dict[str, Any]) -> WorkflowConfig:  # noqa: C901, PLR0912, PLR0915
    """从已解析的 `mapping` 加载 `workflow` 配置(用于文本校验/编辑器等无文件系统场景)."""
    wf_raw = root.get("workflow")
    if not isinstance(wf_raw, dict):
        msg = "Missing required mapping 'workflow'"
        raise WorkflowConfigError(msg, path="workflow")
    wf = cast("Dict[str, Any]", wf_raw)

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
        deps_raw = run_dict.get("deps")
        run_id = str(run_id_raw or "").strip()
        if not run_id:
            msg = "run.id must be a non-empty string"
            raise WorkflowConfigError(msg, path="{}.id".format(item_path))
        if run_id in seen_ids:
            msg = "Duplicate run.id '{}'".format(run_id)
            raise WorkflowConfigError(msg, path="{}.id".format(item_path))
        seen_ids[run_id] = idx
        demand = str(demand_raw or "").strip()
        if not demand:
            msg = "run.demand must be a non-empty string"
            raise WorkflowConfigError(msg, path="{}.demand".format(item_path))

        deps: Tuple[str, ...] = ()
        if deps_raw is not None:
            if not isinstance(deps_raw, list):
                msg = "run.deps must be a list of strings"
                raise WorkflowConfigError(msg, path="{}.deps".format(item_path))
            deps_list: List[str] = []
            for dep_idx, dep in enumerate(cast("List[Any]", deps_raw)):
                dep_path = "{}.deps.{}".format(item_path, dep_idx)
                dep_id = str(dep or "").strip() if isinstance(dep, str) else ""
                if not dep_id:
                    msg = "run.deps items must be non-empty strings"
                    raise WorkflowConfigError(msg, path=dep_path)
                deps_list.append(dep_id)
            if len(set(deps_list)) != len(deps_list):
                msg = "run.deps must not contain duplicates"
                raise WorkflowConfigError(msg, path="{}.deps".format(item_path))
            deps = tuple(deps_list)

        runs.append(WorkflowRun(id=run_id, demand=demand, deps=deps))

    _validate_workflow_deps(runs, seen_ids=seen_ids)

    resources_raw = wf.get("resources", {})
    if resources_raw is None:
        resources_raw = {}
    if not isinstance(resources_raw, dict):
        msg = "workflow.resources must be a mapping"
        raise WorkflowConfigError(msg, path="workflow.resources")
    resources: Dict[str, object] = {}
    for key, value in cast("Dict[Any, Any]", resources_raw).items():
        if not isinstance(key, str) or not key.strip():
            msg = "workflow.resources keys must be non-empty strings"
            raise WorkflowConfigError(msg, path="workflow.resources")
        resources[str(key)] = value

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
        raise WorkflowConfigError(
            msg,
            path="workflow.options.max_concurrency",
        )
    try:
        max_concurrency = int(max_concurrency_raw)
    except (TypeError, ValueError) as exc:
        msg = "workflow.options.max_concurrency must be an integer >= 1"
        raise WorkflowConfigError(
            msg,
            path="workflow.options.max_concurrency",
        ) from exc
    if max_concurrency < 1:
        msg = "workflow.options.max_concurrency must be >= 1"
        raise WorkflowConfigError(msg, path="workflow.options.max_concurrency")

    failure_policy = str(options_dict.get("failure_policy", "all_fail") or "all_fail").strip()
    if failure_policy not in _FAILURE_POLICIES:
        msg = "workflow.options.failure_policy must be one of: {}".format("/".join(_FAILURE_POLICIES))
        raise WorkflowConfigError(msg, path="workflow.options.failure_policy")

    if "share_preload_cache" in options_dict:
        msg = "workflow.options.share_preload_cache was removed; use workflow.options.cache_pool"
        raise WorkflowConfigError(msg, path="workflow.options.share_preload_cache")

    cache_pool: Optional[WorkflowCachePoolOptions] = None
    cache_pool_raw = options_dict.get("cache_pool")
    if cache_pool_raw is not None:
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

        budget_raw = cache_pool_dict.get("budget")
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
            msg = "workflow.options.cache_pool.budget.over_budget_policy must be one of: {}".format(
                "/".join(_CACHE_POOL_OVER_BUDGET_POLICIES)
            )
            raise WorkflowConfigError(msg, path="workflow.options.cache_pool.budget.over_budget_policy")

        budget = WorkflowCachePoolBudget(
            max_entries=max_entries,
            over_budget_policy=over_budget_policy,
        )

        pin_raw = cache_pool_dict.get("pin")
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

        cache_pool = WorkflowCachePoolOptions(
            conflict_policy=conflict_policy,
            release_policy=release_policy,
            budget=budget,
            pin=tuple(pins),
        )

    return WorkflowConfig(
        runs=tuple(runs),
        options=WorkflowOptions(
            max_concurrency=max_concurrency,
            failure_policy=failure_policy,
            cache_pool=cache_pool,
        ),
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
    run_ids = set(seen_ids.keys())
    for idx, run in enumerate(runs):
        item_path = "workflow.runs.{}".format(idx)
        for dep_id in run.deps:
            if dep_id == run.id:
                msg = "run.deps must not include self dependency: '{}'".format(dep_id)
                raise WorkflowConfigError(msg, path="{}.deps".format(item_path))
            if dep_id not in run_ids:
                msg = "Unknown run.deps id '{}'".format(dep_id)
                raise WorkflowConfigError(msg, path="{}.deps".format(item_path))


def _validate_workflow_deps_no_cycles(
    runs: Sequence[WorkflowRun],
    *,
    seen_ids: Mapping[str, int],
) -> None:
    in_degree: Dict[str, int] = {run.id: len(run.deps) for run in runs}
    dependents: Dict[str, List[str]] = {run.id: [] for run in runs}
    for run in runs:
        for dep_id in run.deps:
            dependents[dep_id].append(run.id)

    heap: List[Tuple[int, str]] = []
    for run_id, deg in in_degree.items():
        if deg == 0:
            heap.append((int(seen_ids.get(run_id, 0)), run_id))
    heapq.heapify(heap)

    visited_count = 0
    while heap:
        _order, node_id = heapq.heappop(heap)
        visited_count += 1
        for child_id in dependents.get(node_id, []):
            in_degree[child_id] -= 1
            if in_degree[child_id] == 0:
                heapq.heappush(heap, (int(seen_ids.get(child_id, 0)), child_id))

    if visited_count != len(in_degree):
        cycle_nodes = [run_id for run_id, deg in in_degree.items() if deg > 0]
        msg = "workflow deps must not contain cycles (cycle_nodes={})".format(",".join(sorted(cycle_nodes)))
        raise WorkflowConfigError(msg, path="workflow.runs[*].deps")


__all__ = [
    "WorkflowCachePoolBudget",
    "WorkflowCachePoolOptions",
    "WorkflowCachePoolPin",
    "WorkflowConfig",
    "WorkflowConfigError",
    "WorkflowOptions",
    "WorkflowRun",
    "load_workflow_config",
    "load_workflow_config_from_mapping",
    "resolve_workflow_demand_path",
    "validate_workflow_yaml_text_json",
]
