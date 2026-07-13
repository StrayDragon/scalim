"""工作流资源定义构建助手.

说明:
- 该模块从 `src/scalim/workflow/execute.py` 抽离,用于降低 `execute.py` 体积(`c45`).
"""

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from ..execution import versioned_outputs
from ..spec.ir._workflow import WorkflowIr
from ..vendor.compact.typing_extensionsx import TypeGuard
from .errors import ScalimWorkflowConfigError
from .resources import SheetBookDef


def _is_dict_str_any(value: object) -> TypeGuard[Dict[str, Any]]:
    return isinstance(value, dict)


def _is_pathful_resource_options(opts: Dict[str, Any]) -> Optional[bool]:
    """从 `WorkflowResourceIr.options` 读取 `pathful`;缺省时回退 `legacy` `kind`."""

    if "pathful" in opts:
        return bool(opts.get("pathful"))
    kind = str(opts.get("kind") or "").strip()
    if kind == "xlsx_file":
        return True
    if kind == "xlsx_memory":
        return False
    return None


def options_bool(opts: object, key: str, *, default: bool = False) -> bool:
    if not _is_dict_str_any(opts):
        return bool(default)
    return bool(opts.get(str(key), default))


def build_workflow_resource_defs(  # noqa: C901, PLR0915  # pragma: allow-c901 plan: c45
    workflow_ir: WorkflowIr,
    *,
    workflow_exec_id: str,
) -> Tuple[Dict[str, str], Dict[str, bool], Dict[str, str], Dict[str, SheetBookDef]]:
    workbook_defs: Dict[str, str] = {}
    workbook_allow_formulas_by_id: Dict[str, bool] = {}
    csv_defs: Dict[str, str] = {}
    sheetbook_defs: Dict[str, SheetBookDef] = {}

    layouts_by_root: Dict[str, versioned_outputs.OutputRootLayout] = {}

    def _layout_for_root(output_root: str, *, path: str) -> versioned_outputs.OutputRootLayout:
        root_str = str(output_root or "").strip()
        if not root_str:
            msg = "Output root must be a non-empty string"
            raise ScalimWorkflowConfigError(msg, path=str(path))

        root_norm = str(Path(root_str).expanduser())
        layout = layouts_by_root.get(root_norm)
        if layout is not None:
            return layout

        try:
            layout = versioned_outputs.ensure_output_root_layout(Path(root_norm))
            _ = versioned_outputs.ensure_version_dir(layout, version_id=str(workflow_exec_id))
        except FileExistsError as exc:
            msg = (
                "Version directory already exists (possible concurrent writers or reused workflow_exec_id): "
                "root={!r}, workflow_exec_id={!r}"
            ).format(root_norm, str(workflow_exec_id))
            raise ScalimWorkflowConfigError(msg, path=str(path)) from exc
        except OSError as exc:
            msg = "Failed to prepare output root for workflow run: {}: {}".format(type(exc).__name__, exc)
            raise ScalimWorkflowConfigError(msg, path=str(path)) from exc

        layouts_by_root[root_norm] = layout
        return layout

    for res in workflow_ir.resources:
        res_type = str(res.resource_type)
        if res_type == "book":
            opts = res.options or {}
            if not _is_dict_str_any(opts):
                msg = "Invalid workflow resource options for book: resource_id={!r}".format(str(res.resource_id))
                raise ScalimWorkflowConfigError(msg, path="workflow.resources.books")
            pathful = _is_pathful_resource_options(opts)
            if pathful is True:
                output_root = str(res.path or "")
                layout = _layout_for_root(output_root, path="workflow.resources.books.{}.path".format(str(res.resource_id)))
                final_path = versioned_outputs.book_output_path(layout, version_id=str(workflow_exec_id), book_id=str(res.resource_id))
                workbook_defs[str(res.resource_id)] = str(final_path)
                workbook_allow_formulas_by_id[str(res.resource_id)] = bool(opts.get("allow_formulas", True))
                continue
            if pathful is False:
                budget_obj = opts.get("budget")
                budget_dict: Dict[str, Any] = budget_obj if _is_dict_str_any(budget_obj) else {}
                max_sheets = int(budget_dict.get("max_sheets") or 0)
                max_total_cells = int(budget_dict.get("max_total_cells") or 0)

                export_cfg_obj = opts.get("export_xlsx")
                export_cfg_dict: Dict[str, Any] = export_cfg_obj if _is_dict_str_any(export_cfg_obj) else {}
                export_allow_formulas = bool(export_cfg_dict.get("allow_formulas", True))
                export_path = str(res.path or "").strip() or None
                if export_path is not None:
                    layout = _layout_for_root(export_path, path="workflow.resources.books.{}.export_xlsx.path".format(str(res.resource_id)))
                    final_path = versioned_outputs.book_output_path(layout, version_id=str(workflow_exec_id), book_id=str(res.resource_id))
                    export_path = str(final_path)
                sheetbook_defs[str(res.resource_id)] = SheetBookDef(
                    resource_id=str(res.resource_id),
                    budget_max_sheets=int(max_sheets),
                    budget_max_total_cells=int(max_total_cells),
                    export_path=str(export_path) if export_path is not None else None,
                    export_allow_formulas=bool(export_allow_formulas),
                )
                continue

            msg = "Unknown book identity for book_id={!r}; expected options.pathful or legacy options.kind".format(str(res.resource_id))
            raise ScalimWorkflowConfigError(msg, path="workflow.resources.books.{}".format(str(res.resource_id)))

        if res_type == "workbook":
            output_root = str(res.path or "")
            layout = _layout_for_root(output_root, path="workflow.resources.workbooks.{}.path".format(str(res.resource_id)))
            final_path = versioned_outputs.book_output_path(layout, version_id=str(workflow_exec_id), book_id=str(res.resource_id))
            workbook_defs[str(res.resource_id)] = str(final_path)
            opts = res.options or {}
            workbook_allow_formulas_by_id[str(res.resource_id)] = options_bool(opts, "allow_formulas", default=True)
            continue

        if res_type == "csv":
            output_root = str(res.path or "")
            layout = _layout_for_root(output_root, path="workflow.resources.files.{}.path".format(str(res.resource_id)))
            final_path = versioned_outputs.file_output_path(layout, version_id=str(workflow_exec_id), file_id=str(res.resource_id))
            csv_defs[str(res.resource_id)] = str(final_path)
            continue

        if res_type == "sheetbook":
            opts = res.options or {}
            budget_obj = opts.get("budget")
            sheetbook_budget: Dict[str, Any] = budget_obj if _is_dict_str_any(budget_obj) else {}
            max_sheets = int(sheetbook_budget.get("max_sheets") or 0)
            max_total_cells = int(sheetbook_budget.get("max_total_cells") or 0)

            export_cfg_obj = opts.get("export_xlsx")
            sheetbook_export_cfg: Dict[str, Any] = export_cfg_obj if _is_dict_str_any(export_cfg_obj) else {}
            export_allow_formulas = bool(sheetbook_export_cfg.get("allow_formulas", True))
            export_path = str(res.path or "").strip() or None
            if export_path is not None:
                layout = _layout_for_root(export_path, path="workflow.resources.books.{}.export_xlsx.path".format(str(res.resource_id)))
                final_path = versioned_outputs.book_output_path(layout, version_id=str(workflow_exec_id), book_id=str(res.resource_id))
                export_path = str(final_path)
            sheetbook_defs[str(res.resource_id)] = SheetBookDef(
                resource_id=str(res.resource_id),
                budget_max_sheets=int(max_sheets),
                budget_max_total_cells=int(max_total_cells),
                export_path=str(export_path) if export_path is not None else None,
                export_allow_formulas=bool(export_allow_formulas),
            )
            continue

    return workbook_defs, workbook_allow_formulas_by_id, csv_defs, sheetbook_defs


__all__ = ()
