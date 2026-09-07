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

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ....spec.ir._workflow import WorkflowResourceIr
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
    init_vars: dict[str, Any] | None,
    path_prefix: str,
) -> str | None:
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
    init_vars: dict[str, Any] | None,
    path_prefix: str,
) -> tuple[str, dict[str, Any]]:
    _ = book_id
    is_override = str(path_prefix).startswith("overrides.")
    book_options: dict[str, Any]
    if is_pathful_book(book):
        path_ref = f"{path_prefix}.path" if is_override else f"{path_prefix}.xlsx.path"
        output_root = resolve_yaml_relative_output_path(
            book.path,
            base_dir=str(base_dir),
            init_vars=init_vars,
            path=str(path_ref),
        )
        if Path(str(output_root)).suffix.lower() == ".xlsx":
            msg = (
                f"{path_ref} now expects an output root directory, not a file path. "
                "Migration: set path to './out' and locate outputs via <root>/manifest/latest.json."
            )
            raise ValueError(msg)
        book_options = {
            "pathful": True,
            "allow_formulas": bool(book.allow_formulas),
        }
        return str(output_root), book_options

    # `pathless`: 内存总线;过渡期仍可能带 `export_xlsx`(`override` 路径)
    export_cfg = book.export_xlsx
    output_root = ""
    export_options = None
    if export_cfg is not None:
        export_path_ref = f"{path_prefix}.export_xlsx.path"
        output_root = resolve_yaml_relative_output_path(
            export_cfg.path,
            base_dir=str(base_dir),
            init_vars=init_vars,
            path=str(export_path_ref),
        )
        if Path(str(output_root)).suffix.lower() == ".xlsx":
            msg = (
                f"{export_path_ref} now expects an output root directory, not a file path. "
                "Migration: set path to './out' and locate outputs via <root>/manifest/latest.json."
            )
            raise ValueError(msg)
        export_options = {
            "allow_formulas": bool(export_cfg.allow_formulas),
        }

    book_options = {
        "pathful": False,
    }
    if export_options is not None:
        book_options["export_xlsx"] = export_options
    return str(output_root), book_options


def _file_export_path_and_options(
    file_cfg: FileConfig,
    *,
    file_id: str,
    base_dir: str,
    init_vars: dict[str, Any] | None,
    path_prefix: str,
) -> tuple[str, dict[str, Any]]:
    is_override = str(path_prefix).startswith("overrides.")
    kind = str(file_cfg.kind or "").strip()
    if kind != "csv_file":
        msg = f"Unknown file kind {kind!r} for file_id={str(file_id)!r}"
        path_ref = f"{path_prefix}.kind" if is_override else str(path_prefix)
        err = f"{msg} (path={path_ref})"
        raise ValueError(err)

    path_ref = f"{path_prefix}.path" if is_override else f"{path_prefix}.csv_file.path"
    output_root = resolve_yaml_relative_output_path(
        file_cfg.path,
        base_dir=str(base_dir),
        init_vars=init_vars,
        path=str(path_ref),
    )
    if Path(str(output_root)).suffix.lower() == ".csv":
        msg = (
            f"{path_ref} now expects an output root directory, not a file path. "
            "Migration: set path to './out' and locate outputs via <root>/manifest/latest.json."
        )
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
    init_vars: dict[str, Any] | None,
    overrides_resources: ResourcesOverride | None,
) -> tuple[list[WorkflowResourceIr], dict[str, BookConfig], dict[str, FileConfig]]:
    """编译工作流的有效 `books` 资源并返回:

    - 资源列表(`IR`)
    - 有效 `BookConfig` 映射(`book_id` -> 配置)
    - 有效 `FileConfig` 映射(`file_id` -> 配置)
    """

    msg: str

    workflow_books: dict[str, BookConfig] = dict(wf_obj.resources.books or {})
    workflow_files: dict[str, FileConfig] = dict(wf_obj.resources.files or {})
    demand_books: dict[str, BookConfig] = {}
    demand_files: dict[str, FileConfig] = {}
    demand_base_dir_by_book_id: dict[str, str] = {}
    demand_base_dir_by_file_id: dict[str, str] = {}

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
                    msg = f"Book path-presence mismatch between workflow and demand (book_id={bid!r}, workflow_pathful={wf_pathful!r}, demand_pathful={demand_pathful!r})"  # noqa: E501
                    raise ScalimWorkflowConfigError(msg, path=f"workflow.resources.books.{bid}")
                continue

            existing = demand_books.get(bid)
            if existing is None:
                demand_books[bid] = book
                demand_base_dir_by_book_id[bid] = base_dir
                continue

            # 多个需求声明同一 `book_id` 时,在路径解析后要求配置等价.
            if existing != book:
                msg = f"Conflicting demand book definitions for book_id={bid!r}; declare workflow.resources.books.{bid} to override"
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
                path_prefix=f"resources.books.{bid}",
            )
            current_abs_path = _try_resolve_book_export_abs_path(
                book,
                book_id=bid,
                base_dir=str(base_dir),
                init_vars=init_vars,
                path_prefix=f"resources.books.{bid}",
            )
            if first_abs_path and current_abs_path and str(first_abs_path) != str(current_abs_path):
                msg = (
                    f"Conflicting demand book paths for shared book_id={bid!r} across different YAML dirs; "
                    f"declare workflow.resources.books.{bid} to unify"
                )
                raise ScalimWorkflowConfigError(msg, path="workflow.resources.books")

        for file_id, file_cfg in files.items():
            fid = str(file_id)
            if fid in workflow_files:
                wf_kind = str(workflow_files[fid].kind or "").strip()
                demand_kind = str(file_cfg.kind or "").strip()
                if wf_kind and demand_kind and wf_kind != demand_kind:
                    msg = f"File kind mismatch between workflow and demand (file_id={fid!r}, workflow_kind={wf_kind!r}, demand_kind={demand_kind!r})"  # noqa: E501
                    raise ScalimWorkflowConfigError(msg, path=f"workflow.resources.files.{fid}")
                continue
            existing_file = demand_files.get(fid)
            if existing_file is None:
                demand_files[fid] = file_cfg
                demand_base_dir_by_file_id[fid] = base_dir
                continue
            if existing_file != file_cfg:
                msg = f"Conflicting demand file definitions for file_id={fid!r}; declare workflow.resources.files.{fid} to override"
                raise ScalimWorkflowConfigError(msg, path="workflow.resources.files")

    # 2) 计算有效配置,优先级: 需求 < 工作流 < `overrides`.
    effective_books: dict[str, BookConfig] = {}
    effective_files: dict[str, FileConfig] = {}
    base_dir_by_book_id: dict[str, str] = {}
    base_dir_by_file_id: dict[str, str] = {}
    path_prefix_by_book_id: dict[str, str] = {}
    path_prefix_by_file_id: dict[str, str] = {}

    all_book_ids: set[str] = set()
    all_book_ids.update(demand_books)
    all_book_ids.update(workflow_books)
    all_file_ids: set[str] = set()
    all_file_ids.update(demand_files)
    all_file_ids.update(workflow_files)

    overrides_books_raw = None if overrides_resources is None else overrides_resources.books
    overrides_files_raw = None if overrides_resources is None else overrides_resources.files
    overrides_books: dict[str, BookResourceOverride] | None = None
    overrides_files: dict[str, FileResourceOverride] | None = None
    if overrides_books_raw:
        overrides_books = {}
        for raw_book_id, book_override in overrides_books_raw.items():
            if not isinstance(raw_book_id, str) or not str(raw_book_id).strip():
                msg = "overrides.resources.books keys must be non-empty strings"
                raise ScalimWorkflowConfigError(msg, path="overrides.resources.books")
            bid = str(raw_book_id).strip()
            if bid in overrides_books:
                msg = f"overrides.resources.books has duplicate key: {bid}"
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
                msg = f"overrides.resources.files has duplicate key: {fid}"
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
            path_prefix = f"workflow.resources.books.{bid}"
        elif bid in demand_books:
            book = demand_books[bid]
            base_dir = str(demand_base_dir_by_book_id.get(bid, workflow_base_dir))
            path_prefix = f"resources.books.{bid}"

        # 应用仅 `IO` 的 `overrides.resources.books.<id>` 补丁覆盖(按 `deep-merge` 语义).
        if overrides_books is not None and bid in overrides_books:
            book_override = overrides_books[bid]
            if not isinstance(book_override, BookResourceOverride):
                msg = f"overrides.resources.books.{bid} must be a BookResourceOverride"
                raise ScalimWorkflowConfigError(msg, path=f"overrides.resources.books.{bid}")
            if book is None:
                book = BookConfig(kind="")
                base_dir = str(workflow_base_dir)
            book = _resource_override_ssot.apply_book_resource_override(book, book_override, path=f"overrides.resources.books.{bid}")
            path_prefix = f"overrides.resources.books.{bid}"

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
            path_prefix = f"workflow.resources.files.{fid}"
        elif fid in demand_files:
            file_cfg = demand_files[fid]
            base_dir = str(demand_base_dir_by_file_id.get(fid, workflow_base_dir))
            path_prefix = f"resources.files.{fid}"

        if overrides_files is not None and fid in overrides_files:
            file_override = overrides_files[fid]
            if not isinstance(file_override, FileResourceOverride):
                msg = f"overrides.resources.files.{fid} must be a FileResourceOverride"
                raise ScalimWorkflowConfigError(msg, path=f"overrides.resources.files.{fid}")
            if file_cfg is None:
                file_cfg = FileConfig(kind="")
                base_dir = str(workflow_base_dir)
            file_cfg = _resource_override_ssot.apply_file_resource_override(
                file_cfg, file_override, path=f"overrides.resources.files.{fid}"
            )
            path_prefix = f"overrides.resources.files.{fid}"

        if file_cfg is None or base_dir is None:
            continue  # pragma: no cover  # pragma: allow-no-cover unreachable: all_file_ids derived from workflow/demand/overrides
        effective_files[fid] = file_cfg
        base_dir_by_file_id[fid] = base_dir
        path_prefix_by_file_id[fid] = path_prefix

    resources: list[WorkflowResourceIr] = []
    for bid, book in sorted(effective_books.items(), key=lambda kv: str(kv[0])):
        base_dir = base_dir_by_book_id.get(str(bid), str(workflow_base_dir))
        prefix = path_prefix_by_book_id.get(str(bid)) or (
            f"workflow.resources.books.{bid!s}" if str(bid) in workflow_books else f"resources.books.{bid!s}"
        )
        try:
            export_path, options = _book_export_path_and_options(
                book,
                book_id=str(bid),
                base_dir=str(base_dir),
                init_vars=init_vars,
                path_prefix=prefix,
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
            f"workflow.resources.files.{fid!s}" if str(fid) in workflow_files else f"resources.files.{fid!s}"
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
    init_vars: dict[str, Any] | None,
    path_prefix: str,
) -> str | None:
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
    init_vars: dict[str, Any] | None,
    path_prefix: str,
) -> tuple[str, dict[str, Any]]:
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
    init_vars: dict[str, Any] | None,
    path_prefix: str,
) -> tuple[str, dict[str, Any]]:
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
    init_vars: dict[str, Any] | None,
    overrides_resources: ResourcesOverride | None,
) -> tuple[list[WorkflowResourceIr], dict[str, BookConfig], dict[str, FileConfig]]:
    return _compile_workflow_resources(
        wf_obj,
        workflow_base_dir=workflow_base_dir,
        demand_cfg_by_run_id=demand_cfg_by_run_id,
        demand_yaml_paths_by_run_id=demand_yaml_paths_by_run_id,
        init_vars=init_vars,
        overrides_resources=overrides_resources,
    )
