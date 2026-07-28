from typing import Any, ClassVar, Dict, List, Optional, Tuple

from .....vendor.dataclassesx import dataclass
from .....vendor.dataclassesx import field as dataclass_field
from ...init_var_nodes import OptionalPathNode
from ..constants import DEFAULT_OUTPUT_ENCODING, schema_meta, schema_omit, schema_ref
from ..output_enums import (
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
            "description": "输出 root 目录(相对路径以 YAML 文件所在目录为基准;自动 mkdir 父目录)",
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
    "description": "输出 root 目录(支持静态字符串 或 {$init_var: <name>} 动态注入)",
    "examples": [
        "./output",
        {"$init_var": "output_root"},
    ],
}


@dataclass(frozen=True)
class BookExportXlsxConfig:
    SCHEMA_NAME: ClassVar[str] = "book_export_xlsx"
    SCHEMA_REQUIRED: ClassVar[Tuple[str, ...]] = ("path",)
    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False

    path: OptionalPathNode = dataclass_field(
        default=None,
        metadata=schema_meta(
            schema=_PATH_OR_INIT_VAR_SCHEMA,
            desc="导出 xlsx 的输出 root 目录(字符串或 {$init_var: <name>})",
        ),
    )

    allow_formulas: bool = dataclass_field(
        default=True,
        metadata=schema_meta(
            desc="允许 Excel 公式(默认 true;不可信输入显式设为 false 以启用转义防护)",
            md="允许 Excel 公式(默认 true;不可信输入显式设为 false 以启用转义防护).",
            default=True,
            examples=[True],
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
class BookXlsxConfig:
    """统一 `book` `identity`: 有 `path`=落盘; 无 `path`=内存总线."""

    SCHEMA_NAME: ClassVar[str] = "book_xlsx"
    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False

    path: OptionalPathNode = dataclass_field(
        default=None,
        metadata=schema_meta(
            schema=_PATH_OR_INIT_VAR_SCHEMA,
            desc="可选输出 root 目录(有 path=落盘;无 path=内存总线;字符串或 {$init_var: <name>})",
            md=(
                "可选输出 root 目录.\n\n"
                "- 有 `path`: 版本化落盘\n"
                "- 无 `path`: 内存总线\n"
                "- 禁止在此分支使用 `export_xlsx`/`write_defaults`/`budget`\n"
                "- 旧别名 `xlsx_file`/`xlsx_memory`/`export_xlsx` 已硬删(出现即 `fail-fast`)"
            ),
        ),
    )

    allow_formulas: bool = dataclass_field(
        default=True,
        metadata=schema_meta(
            desc="允许 Excel 公式(仅导出时有意义;默认 true;不可信输入显式设为 false)",
            md="允许 Excel 公式(仅有 path 导出时有意义;默认 true;不可信输入显式设为 false).",
            default=True,
            examples=[True],
        ),
    )


@dataclass(frozen=True)
class BookConfig:
    SCHEMA_NAME: ClassVar[str] = "book"
    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    SCHEMA_ALL_OF: ClassVar[List[Dict[str, Any]]] = [
        {
            "anyOf": [
                {"required": ["$import"]},
                {"required": ["xlsx"]},
            ]
        },
    ]

    kind: str = dataclass_field(
        default="",
        metadata=schema_omit(),
    )

    path: OptionalPathNode = dataclass_field(
        default=None,
        metadata=schema_omit(),
    )

    export_xlsx: Optional[BookExportXlsxConfig] = dataclass_field(
        default=None,
        metadata=schema_omit(),
    )

    allow_formulas: bool = dataclass_field(
        default=False,
        metadata=schema_omit(),
    )

    write_defaults: Optional[BookWriteDefaultsConfig] = dataclass_field(
        default=None,
        metadata=schema_omit(),
    )

    xlsx: Optional[BookXlsxConfig] = dataclass_field(
        default=None,
        metadata=schema_meta(
            desc="xlsx: 统一 book identity(有 path=落盘;无 path=内存总线)",
            md=(
                "`xlsx`: 统一 `book` identity(唯一编写面 `SSOT`).\n\n"
                "- 有 `path`: 版本化落盘\n"
                "- 无 `path`: 内存总线(`book_sheet_rows`)\n"
                "- 可选: `allow_formulas`(导出相关)\n"
                "- `write_defaults` 在 Python `BookWritePolicy`\n"
                "- `budget` 已移除(残留 fail-fast,删字段;内存交宿主限制)\n"
                "- 已移除别名: `xlsx_file` / `xlsx_memory`(出现即 `fail-fast`)"
            ),
            ref="book_xlsx",
        ),
    )


@dataclass(frozen=True)
class FileConfig:
    SCHEMA_NAME: ClassVar[str] = "file"
    SCHEMA_REQUIRED: ClassVar[Tuple[str, ...]] = ("csv_file",)
    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False

    kind: str = dataclass_field(
        default="",
        metadata=schema_omit(),
    )

    path: OptionalPathNode = dataclass_field(
        default=None,
        metadata=schema_omit(),
    )

    encoding: str = dataclass_field(
        default=DEFAULT_OUTPUT_ENCODING,
        metadata=schema_omit(),
    )

    csv_file: Optional["FileCsvFileConfig"] = dataclass_field(
        default=None,
        metadata=schema_meta(
            desc="csv_file: CSV 文件导出配置",
            md="csv_file: CSV 文件导出配置.\n\n- 必填: `path`\n- 可选: `encoding`",
            ref="file_csv_file",
        ),
    )


@dataclass(frozen=True)
class FileCsvFileConfig:
    SCHEMA_NAME: ClassVar[str] = "file_csv_file"
    SCHEMA_REQUIRED: ClassVar[Tuple[str, ...]] = ("path",)
    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False

    path: OptionalPathNode = dataclass_field(
        default=None,
        metadata=schema_meta(
            schema=_PATH_OR_INIT_VAR_SCHEMA,
            desc="输出 root 目录(字符串或 {$init_var: <name>})",
        ),
    )

    encoding: str = dataclass_field(
        default=DEFAULT_OUTPUT_ENCODING,
        metadata=schema_meta(
            desc="文件编码(默认 utf-8)",
            md="文件编码(默认 `utf-8`).",
            default=DEFAULT_OUTPUT_ENCODING,
            examples=[DEFAULT_OUTPUT_ENCODING],
        ),
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
                "- 唯一 authoring SSOT: `xlsx`(可选 `path`; 有 path=落盘; 无 path=内存总线)\n"
                "- 相对路径解析基准: 声明该资源的 YAML 文件所在目录\n"
                "- `outputs[*].to.book` 引用该 mapping 的 key"
            ),
            additional_props=schema_ref("book"),
            min_props=0,
        ),
    )

    files: Dict[str, FileConfig] = dataclass_field(
        default_factory=dict,
        metadata=schema_meta(
            desc="files 资源映射(文件输出资源; key 为 file_id)",
            md=(
                "files 资源映射(文件输出资源; key 为 `file_id`).\n\n"
                "- v1 稳定支持: `kind=csv_file`\n"
                "- 相对路径解析基准: 声明该资源的 YAML 文件所在目录\n"
                "- `outputs[*].to.file` 引用该 mapping 的 key"
            ),
            additional_props=schema_ref("file"),
            min_props=0,
        ),
    )


__all__ = ()
