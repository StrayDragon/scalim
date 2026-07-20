# pragma: allow-c901-file plan: c75
"""`workflow` 编译: `resources` 编译 (路径解析 + `IR` 构建).

职责:
- 基于 `workflow` / `demand` / `overrides` 合并得到有效的 `BookConfig` / `FileConfig`.
- 将有效资源解析为 `WorkflowResourceIr` (导出路径与 `options`).

边界:
- 本模块不读取 `demand YAML` (不进行 `YamlDemandLoader.load`).
- 允许进行路径解析 (例如 `Path.resolve` 与输出路径归一化), 但不执行实际写入.
- 本模块不负责 `DAG` 构建 / `outputs` 写入节点注入 / `runtime options` 解析.
"""

from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Set, Tuple

from ....spec.ir._workflow import WorkflowResourceIr
from ..book_resource_policy import ResourcesPolicy
from ..runtime.contracts import BookResourceOverride, FileResourceOverride, ResourcesOverride
from ..runtime.output_path_resolve import resolve_yaml_relative_output_path
from ..schema_dsl.constants import DEFAULT_OUTPUT_ENCODING
from ..schema_dsl.models import BookConfig, DemandConfig, FileConfig
from ..workflow import ScalimWorkflowConfigError, WorkflowConfig
from . import resource_override as _resource_override_ssot
from .book_identity import is_pathful_book

__all__ = ()


def _as_abs_path(raw_path: str) -> str:
    return str(Path(str(raw_path)).expanduser().resolve(strict=False))


def _try_resolve_book_export_abs_path(
    book: BookConfig,
    *,
    book_id: str,
    base_dir: str,
    init_vars: Optional[Dict[str, Any]],
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


def _demand_base_dir(demand_yaml_path: str) -> Path:
    p = Path(str(demand_yaml_path or "")).expanduser().resolve(strict=False)
    return p.parent


def _book_export_path_and_options(
    book: BookConfig,
    *,
    book_id: str,
    base_dir: str,
    init_vars: Optional[Dict[str, Any]],
    path_prefix: str,
    resources_policy: Optional[ResourcesPolicy] = None,
) -> Tuple[str, Dict[str, Any]]:
    is_override = str(path_prefix).startswith("overrides.")
    book_options: Dict[str, Any]
    if is_pathful_book(book):
        path_ref = "{}.path".format(path_prefix) if is_override else "{}.xlsx.path".format(path_prefix)
        output_root = resolve_yaml_relative_output_path(
            book.path,
            base_dir=str(base_dir),
            init_vars=init_vars,
            path=str(path_ref),
        )
        if Path(str(output_root)).suffix.lower() == ".xlsx":
            msg = (
                "{} now expects an output root directory, not a file path. "
                "Migration: set path to './out' and locate outputs via <root>/manifest/latest.json."
            ).format(path_ref)
            raise ValueError(msg)
        book_options = {
            "pathful": True,
            "allow_formulas": bool(book.allow_formulas),
        }
        return str(output_root), book_options

    # `pathless`: 内存总线;过渡期仍可能带 `export_xlsx`(`override` 路径)
    budget_mapping = None
    if isinstance(resources_policy, ResourcesPolicy):
        budget_mapping = resources_policy.budget_policy_for(str(book_id)).as_options_mapping()

    export_cfg = book.export_xlsx
    output_root = ""
    export_options = None
    if export_cfg is not None:
        export_path_ref = "{}.export_xlsx.path".format(path_prefix)
        output_root = resolve_yaml_relative_output_path(
            export_cfg.path,
            base_dir=str(base_dir),
            init_vars=init_vars,
            path=str(export_path_ref),
        )
        if Path(str(output_root)).suffix.lower() == ".xlsx":
            msg = (
                "{} now expects an output root directory, not a file path. "
                "Migration: set path to './out' and locate outputs via <root>/manifest/latest.json."
            ).format(export_path_ref)
            raise ValueError(msg)
        export_options = {
            "allow_formulas": bool(export_cfg.allow_formulas),
        }

    book_options = {
        "pathful": False,
    }
    if budget_mapping is not None:
        book_options["budget"] = dict(budget_mapping)
    if export_options is not None:
        book_options["export_xlsx"] = export_options
    return str(output_root), book_options


def _file_export_path_and_options(
    file_cfg: FileConfig,
    *,
    file_id: str,
    base_dir: str,
    init_vars: Optional[Dict[str, Any]],
    path_prefix: str,
) -> Tuple[str, Dict[str, Any]]:
    is_override = str(path_prefix).startswith("overrides.")
    kind = str(file_cfg.kind or "").strip()
    if kind != "csv_file":
        msg = "Unknown file kind {!r} for file_id={!r}".format(kind, str(file_id))
        path_ref = "{}.kind".format(path_prefix) if is_override else str(path_prefix)
        err = "{} (path={})".format(msg, path_ref)
        raise ValueError(err)

    path_ref = "{}.path".format(path_prefix) if is_override else "{}.csv_file.path".format(path_prefix)
    output_root = resolve_yaml_relative_output_path(
        file_cfg.path,
        base_dir=str(base_dir),
        init_vars=init_vars,
        path=str(path_ref),
    )
    if Path(str(output_root)).suffix.lower() == ".csv":
        msg = (
            "{} now expects an output root directory, not a file path. "
            "Migration: set path to './out' and locate outputs via <root>/manifest/latest.json."
        ).format(path_ref)
        raise ValueError(msg)
    return str(output_root), {
        "kind": "csv_file",
        "encoding": str(file_cfg.encoding or DEFAULT_OUTPUT_ENCODING),
    }


def _compile_workflow_resources(  # noqa: C901, PLR0912, PLR0915
    wf_obj: WorkflowConfig,
    *,
    workflow_base_dir: Path,
    demand_cfg_by_run_id: Mapping[str, DemandConfig],
    demand_yaml_paths_by_run_id: Mapping[str, str],
    init_vars: Optional[Dict[str, Any]],
    overrides_resources: Optional[ResourcesOverride],
    resources_policy: Optional[ResourcesPolicy] = None,
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
                # 工作流声明同名 `book_id` 时,要求与需求侧的 `pathful`/`pathless` 身份兼容.
                wf_pathful = is_pathful_book(workflow_books[bid])
                demand_pathful = is_pathful_book(book)
                if wf_pathful != demand_pathful:
                    msg = (
                        "Book path-presence mismatch between workflow and demand (book_id={!r}, workflow_pathful={!r}, demand_pathful={!r})"
                    ).format(bid, wf_pathful, demand_pathful)
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
    overrides_books: Optional[Dict[str, BookResourceOverride]] = None
    overrides_files: Optional[Dict[str, FileResourceOverride]] = None
    if overrides_books_raw:
        overrides_books = {}
        for raw_book_id, book_override in overrides_books_raw.items():
            if not isinstance(raw_book_id, str) or not str(raw_book_id).strip():
                msg = "overrides.resources.books keys must be non-empty strings"
                raise ScalimWorkflowConfigError(msg, path="overrides.resources.books")
            bid = str(raw_book_id).strip()
            if bid in overrides_books:
                msg = "overrides.resources.books has duplicate key: {}".format(bid)
                raise ScalimWorkflowConfigError(msg, path="overrides.resources.books")
            overrides_books[bid] = book_override
        all_book_ids.update(overrides_books.keys())
    if overrides_files_raw:
        overrides_files = {}
        for raw_file_id, file_override in overrides_files_raw.items():
            if not isinstance(raw_file_id, str) or not str(raw_file_id).strip():
                msg = "overrides.resources.files keys must be non-empty strings"
                raise ScalimWorkflowConfigError(msg, path="overrides.resources.files")
            fid = str(raw_file_id).strip()
            if fid in overrides_files:
                msg = "overrides.resources.files has duplicate key: {}".format(fid)
                raise ScalimWorkflowConfigError(msg, path="overrides.resources.files")
            overrides_files[fid] = file_override
        all_file_ids.update(overrides_files.keys())

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
        if overrides_books is not None and bid in overrides_books:
            book_override = overrides_books[bid]
            if not isinstance(book_override, BookResourceOverride):
                msg = "overrides.resources.books.{} must be a BookResourceOverride".format(bid)
                raise ScalimWorkflowConfigError(msg, path="overrides.resources.books.{}".format(bid))
            if book is None:
                book = BookConfig(kind="")
                base_dir = str(workflow_base_dir)
            book = _resource_override_ssot.apply_book_resource_override(
                book, book_override, path="overrides.resources.books.{}".format(bid)
            )
            path_prefix = "overrides.resources.books.{}".format(bid)

        if book is None or base_dir is None:
            continue  # pragma: no cover  # pragma: allow-no-cover unreachable: all_book_ids derived from workflow/demand/overrides
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

        if overrides_files is not None and fid in overrides_files:
            file_override = overrides_files[fid]
            if not isinstance(file_override, FileResourceOverride):
                msg = "overrides.resources.files.{} must be a FileResourceOverride".format(fid)
                raise ScalimWorkflowConfigError(msg, path="overrides.resources.files.{}".format(fid))
            if file_cfg is None:
                file_cfg = FileConfig(kind="")
                base_dir = str(workflow_base_dir)
            file_cfg = _resource_override_ssot.apply_file_resource_override(
                file_cfg, file_override, path="overrides.resources.files.{}".format(fid)
            )
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
                resources_policy=resources_policy,
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


def as_abs_path(raw_path: str) -> str:
    return _as_abs_path(raw_path)


def try_resolve_book_export_abs_path(
    book: BookConfig,
    *,
    book_id: str,
    base_dir: str,
    init_vars: Optional[Dict[str, Any]],
    path_prefix: str,
) -> Optional[str]:
    return _try_resolve_book_export_abs_path(
        book,
        book_id=book_id,
        base_dir=base_dir,
        init_vars=init_vars,
        path_prefix=path_prefix,
    )


def demand_base_dir(demand_yaml_path: str) -> Path:
    return _demand_base_dir(demand_yaml_path)


def book_export_path_and_options(
    book: BookConfig,
    *,
    book_id: str,
    base_dir: str,
    init_vars: Optional[Dict[str, Any]],
    path_prefix: str,
) -> Tuple[str, Dict[str, Any]]:
    return _book_export_path_and_options(
        book,
        book_id=book_id,
        base_dir=base_dir,
        init_vars=init_vars,
        path_prefix=path_prefix,
    )


def file_export_path_and_options(
    file_cfg: FileConfig,
    *,
    file_id: str,
    base_dir: str,
    init_vars: Optional[Dict[str, Any]],
    path_prefix: str,
) -> Tuple[str, Dict[str, Any]]:
    return _file_export_path_and_options(
        file_cfg,
        file_id=file_id,
        base_dir=base_dir,
        init_vars=init_vars,
        path_prefix=path_prefix,
    )


def compile_workflow_resources(
    wf_obj: WorkflowConfig,
    *,
    workflow_base_dir: Path,
    demand_cfg_by_run_id: Mapping[str, DemandConfig],
    demand_yaml_paths_by_run_id: Mapping[str, str],
    init_vars: Optional[Dict[str, Any]],
    overrides_resources: Optional[ResourcesOverride],
    resources_policy: Optional[ResourcesPolicy] = None,
) -> Tuple[List[WorkflowResourceIr], Dict[str, BookConfig], Dict[str, FileConfig]]:
    return _compile_workflow_resources(
        wf_obj,
        workflow_base_dir=workflow_base_dir,
        demand_cfg_by_run_id=demand_cfg_by_run_id,
        demand_yaml_paths_by_run_id=demand_yaml_paths_by_run_id,
        init_vars=init_vars,
        overrides_resources=overrides_resources,
        resources_policy=resources_policy,
    )
