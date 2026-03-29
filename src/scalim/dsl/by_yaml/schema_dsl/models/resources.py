from typing import Any, ClassVar, Dict, List, Optional, Tuple

from .....vendor.dataclassesx import dataclass
from .....vendor.dataclassesx import field as dataclass_field
from ..constants import schema_meta, schema_ref
from ..output_enums import (
    BOOK_KINDS,
    BOOK_WRITE_ALIGN_BY_ENUM,
    BOOK_WRITE_HEADER_POLICY_ENUM,
    BOOK_WRITE_MODE_ENUM,
    BOOK_WRITE_ON_CONFLICT_ENUM,
    BOOK_WRITE_ON_MISMATCH_ENUM,
    DEFAULT_BOOK_WRITE_ALIGN_BY,
    DEFAULT_BOOK_WRITE_HEADER_POLICY,
    DEFAULT_BOOK_WRITE_MODE,
    DEFAULT_BOOK_WRITE_ON_CONFLICT,
    DEFAULT_BOOK_WRITE_ON_MISMATCH,
)

_PATH_OR_INIT_VAR_SCHEMA = {
    "oneOf": [
        {
            "type": "string",
            "minLength": 1,
            "description": "输出文件路径(相对路径以 YAML 文件所在目录为基准;自动 mkdir 父目录)",
        },
        {
            "type": "object",
            "properties": {
                "$init_var": {
                    "type": "string",
                    "minLength": 1,
                    "description": "运行时变量名(编译期解析为 init_vars[<name>])",
                }
            },
            "required": ["$init_var"],
            "additionalProperties": False,
            "description": "运行时动态路径: {$init_var: <name>}",
        },
    ],
    "description": "输出文件路径(支持静态字符串 或 {$init_var: <name>} 动态注入)",
    "examples": [
        "./output/report.xlsx",
        {"$init_var": "output_path"},
    ],
}


@dataclass(frozen=True)
class BookBudgetConfig:
    SCHEMA_NAME: ClassVar[str] = "book_budget"
    SCHEMA_REQUIRED: ClassVar[Tuple[str, ...]] = ("max_sheets", "max_total_cells")
    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False

    max_sheets: int = dataclass_field(
        default=0,
        metadata=schema_meta(
            desc="sheet 数量预算(>=1)",
            md="sheet 数量预算(>=1).",
            min=1,
            examples=[64],
        ),
    )

    max_total_cells: int = dataclass_field(
        default=0,
        metadata=schema_meta(
            desc="总 cell 数预算(>=1)",
            md="总 cell 数预算(>=1).",
            min=1,
            examples=[1000000],
        ),
    )


@dataclass(frozen=True)
class BookExportXlsxConfig:
    SCHEMA_NAME: ClassVar[str] = "book_export_xlsx"
    SCHEMA_REQUIRED: ClassVar[Tuple[str, ...]] = ("path",)
    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False

    path: Any = dataclass_field(
        default=None,
        metadata=schema_meta(
            schema=_PATH_OR_INIT_VAR_SCHEMA,
            desc="导出 xlsx 的输出路径(字符串或 {$init_var: <name>})",
        ),
    )

    write_lock: bool = dataclass_field(
        default=False,
        metadata=schema_meta(
            desc="写锁(导出时;默认 false)",
            md="写锁(导出时;默认 false).",
            default=False,
            examples=[False],
        ),
    )

    allow_formulas: bool = dataclass_field(
        default=False,
        metadata=schema_meta(
            desc="允许 Excel 公式(可信输入显式 opt-out;默认 false)",
            md="允许 Excel 公式(可信输入显式 opt-out;默认 false).",
            default=False,
            examples=[False],
        ),
    )


@dataclass(frozen=True)
class BookWriteDefaultsConfig:
    SCHEMA_NAME: ClassVar[str] = "book_write_defaults"
    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False

    mode: str = dataclass_field(
        default=DEFAULT_BOOK_WRITE_MODE,
        metadata=schema_meta(
            desc="写入语义(sheet/append)",
            md="写入语义.\n\n- `sheet`: 写入/覆盖某个 sheet\n- `append`: 追加写入某个 sheet",
            choices=list(BOOK_WRITE_MODE_ENUM),
            default=DEFAULT_BOOK_WRITE_MODE,
            examples=[DEFAULT_BOOK_WRITE_MODE],
        ),
    )

    align_by: str = dataclass_field(
        default=DEFAULT_BOOK_WRITE_ALIGN_BY,
        metadata=schema_meta(
            desc="字段对齐策略(field_id/header;仅 append 生效)",
            md=(
                "字段对齐策略(仅 `mode=append` 生效).\n\n"
                "- `field_id`: 按 field_id 对齐(忽略 header 名)\n"
                "- `header`: 按 header 名对齐(严格匹配)"
            ),
            choices=list(BOOK_WRITE_ALIGN_BY_ENUM),
            default=DEFAULT_BOOK_WRITE_ALIGN_BY,
            examples=[DEFAULT_BOOK_WRITE_ALIGN_BY],
        ),
    )

    header_policy: str = dataclass_field(
        default=DEFAULT_BOOK_WRITE_HEADER_POLICY,
        metadata=schema_meta(
            desc="表头策略(once/always/never;仅 append 生效)",
            md="表头策略(仅 `mode=append` 生效).\n\n- `once`: 只在第一段输出表头\n- `always`: 每段都输出表头\n- `never`: 不输出表头",
            choices=list(BOOK_WRITE_HEADER_POLICY_ENUM),
            default=DEFAULT_BOOK_WRITE_HEADER_POLICY,
            examples=[DEFAULT_BOOK_WRITE_HEADER_POLICY],
        ),
    )

    on_mismatch: str = dataclass_field(
        default=DEFAULT_BOOK_WRITE_ON_MISMATCH,
        metadata=schema_meta(
            desc="字段不匹配策略(error/warn/skip;仅 append 生效)",
            md="字段不匹配策略(仅 `mode=append` 生效).\n\n- `error`: 失败\n- `warn`: 告警并继续\n- `skip`: 跳过该段写入",
            choices=list(BOOK_WRITE_ON_MISMATCH_ENUM),
            default=DEFAULT_BOOK_WRITE_ON_MISMATCH,
            examples=[DEFAULT_BOOK_WRITE_ON_MISMATCH],
        ),
    )

    on_conflict: str = dataclass_field(
        default=DEFAULT_BOOK_WRITE_ON_CONFLICT,
        metadata=schema_meta(
            desc="sheet 冲突策略(error/overwrite/skip;仅 sheet 生效)",
            md="sheet 冲突策略(仅 `mode=sheet` 生效).\n\n- `error`: 失败\n- `overwrite`: 覆盖\n- `skip`: 跳过",
            choices=list(BOOK_WRITE_ON_CONFLICT_ENUM),
            default=DEFAULT_BOOK_WRITE_ON_CONFLICT,
            examples=[DEFAULT_BOOK_WRITE_ON_CONFLICT],
        ),
    )


@dataclass(frozen=True)
class BookConfig:
    SCHEMA_NAME: ClassVar[str] = "book"
    SCHEMA_REQUIRED: ClassVar[Tuple[str, ...]] = ("kind",)
    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    SCHEMA_ALL_OF: ClassVar[List[Dict[str, Any]]] = [
        {
            "if": {"properties": {"kind": {"const": "xlsx_file"}}},
            "then": {
                "required": ["path"],
                "properties": {
                    "budget": {"not": {}},
                    "export_xlsx": {"not": {}},
                },
            },
        },
        {
            "if": {"properties": {"kind": {"const": "xlsx_memory"}}},
            "then": {
                "required": ["budget"],
                "properties": {
                    "path": {"not": {}},
                    "allow_formulas": {"not": {}},
                    "write_lock": {"not": {}},
                },
            },
        },
    ]

    kind: str = dataclass_field(
        default="",
        metadata=schema_meta(
            desc="book kind(xlsx_file/xlsx_memory)",
            md="book kind.\n\n- `xlsx_file`: 导出为单个 `.xlsx` 文件\n- `xlsx_memory`: workflow-scope 内存工作簿(可选导出)",
            choices=list(BOOK_KINDS),
            examples=["xlsx_file"],
        ),
    )

    path: Any = dataclass_field(
        default=None,
        metadata=schema_meta(
            schema=_PATH_OR_INIT_VAR_SCHEMA,
            desc="xlsx_file: 输出路径(字符串或 {$init_var: <name>})",
        ),
    )

    budget: Optional[BookBudgetConfig] = dataclass_field(
        default=None,
        metadata=schema_meta(desc="xlsx_memory: 预算配置(必填)", ref="book_budget"),
    )

    export_xlsx: Optional[BookExportXlsxConfig] = dataclass_field(
        default=None,
        metadata=schema_meta(desc="xlsx_memory: 可选导出配置", ref="book_export_xlsx"),
    )

    allow_formulas: bool = dataclass_field(
        default=False,
        metadata=schema_meta(
            desc="xlsx_file: 允许 Excel 公式(可信输入显式 opt-out;默认 false)",
            md="xlsx_file: 允许 Excel 公式(可信输入显式 opt-out;默认 false).",
            default=False,
            examples=[False],
        ),
    )

    write_lock: bool = dataclass_field(
        default=False,
        metadata=schema_meta(
            desc="xlsx_file: 写锁(默认 false)",
            md="xlsx_file: 写锁(默认 false).",
            default=False,
            examples=[False],
        ),
    )

    write_defaults: Optional[BookWriteDefaultsConfig] = dataclass_field(
        default=None,
        metadata=schema_meta(desc="可选:默认写入语义与冲突策略", ref="book_write_defaults"),
    )


@dataclass(frozen=True)
class ResourcesConfig:
    SCHEMA_NAME: ClassVar[str] = "resources"
    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False

    books: Dict[str, BookConfig] = dataclass_field(
        default_factory=dict,
        metadata=schema_meta(
            desc="books 资源映射(Excel book; key 为 book_id)",
            md=(
                "books 资源映射(Excel book; key 为 `book_id`).\n\n"
                "- 对外稳定术语: `book`\n"
                "- `kind` 选择实现策略(`xlsx_file`/`xlsx_memory`)\n"
                "- 相对路径解析基准: 声明该资源的 YAML 文件所在目录\n"
                "- `outputs_defaults.to.book` / `outputs[*].to.book` 引用该 mapping 的 key"
            ),
            additional_props=schema_ref("book"),
            min_props=0,
        ),
    )


__all__ = []
