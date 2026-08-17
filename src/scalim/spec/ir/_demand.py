from collections.abc import Mapping as MappingABC
from types import MappingProxyType
from typing import Any, Dict, List, Mapping, Optional, Sequence

from ...vendor.dataclassesx import dataclass
from ._fields import FieldIr, SupportedFieldIr
from ._sources import MainSourceIr, SourceIr
from .presentation import ExportProfileIr


@dataclass(frozen=True)
class DemandIr:
    """
    需求(IR): IR 层的顶层结构, 包含完整的数据需求定义, 包括数据源、字段、关系等
    """

    sources: Mapping[str, SourceIr]
    """
    数据源目录(`source_id` -> `SourceIr`);`SourceIr` 的 SSOT.

    运行时策略(`LookupChunking` / `SourceCache` / `RowsReuse`)只覆盖本目录.
    `FieldIr.source` / `LookupStepIr.to_source` 是图句柄,按 `source_id` 回这里解析.
    运行时为 `MappingProxyType` — 浅不可变.
    """

    fields: Mapping[str, SupportedFieldIr]
    """
    字段字典(内部使用:`field_key` -> `SupportedFieldIr`).
    运行时为 `MappingProxyType` — 浅不可变.
    """

    main_source: MainSourceIr
    """
    主数据源对象 (入口数据源)
    """

    row_id_key: str = "row_id"
    """
    内部行标识字段名 (框架维护)
    """

    batch_size_hint: Optional[int] = 1000
    """
    建议的批次大小
    """

    name: str = ""
    """
    需求模型名称 (可选)
    """

    export_profile: Optional[ExportProfileIr] = None
    """
    导出配置
    """

    def __post_init__(self) -> None:
        state: Dict[str, Any] = vars(self)

        sources_raw = state.get("sources")
        if not isinstance(sources_raw, MappingABC):
            msg = "DemandIr.sources must be a mapping from source_id to SourceIr"
            raise TypeError(msg)
        if not isinstance(sources_raw, MappingProxyType):
            object.__setattr__(self, "sources", MappingProxyType(dict(self.sources)))

        fields_raw = state.get("fields")
        if not isinstance(fields_raw, MappingABC):
            msg = "DemandIr.fields must be a mapping from field_key to SupportedFieldIr"
            raise TypeError(msg)
        if not isinstance(fields_raw, MappingProxyType):
            object.__setattr__(self, "fields", MappingProxyType(dict(self.fields)))

        if self.main_source.source_id in self.sources:
            msg = f"主数据源 {self.main_source.source_id!r} 不应出现在 sources 中"
            raise ValueError(msg)

        # 验证字段引用的数据源存在
        for field_key, field_spec in self.fields.items():
            if isinstance(field_spec, FieldIr):
                source_id = field_spec.source.source_id
                if source_id != self.main_source.source_id and source_id not in self.sources:
                    msg = f"字段 {field_key!r} 引用的数据源 {source_id!r} 不存在"
                    raise ValueError(msg)

    def __getstate__(self) -> Dict[str, Any]:
        state = dict(self.__dict__)
        sources = state.get("sources")
        if isinstance(sources, MappingProxyType):
            state["sources"] = dict(sources)
        fields = state.get("fields")
        if isinstance(fields, MappingProxyType):
            state["fields"] = dict(fields)
        return state

    def __setstate__(self, state: Dict[str, Any]) -> None:
        for key, value in state.items():
            object.__setattr__(self, key, value)
        self.__post_init__()

    @classmethod
    def from_irs(
        cls,
        sources: List[SourceIr],
        fields: Sequence[SupportedFieldIr],
        main_source: MainSourceIr,
        batch_size_hint: Optional[int] = 1000,
        name: str = "",
        export_profile: Optional[ExportProfileIr] = None,
        row_id_key: str = "row_id",
    ) -> "DemandIr":
        """从列表构造(推荐方式): 自动转换为字典并检测重名冲突

        参数:
            `sources`: 数据源列表
            `fields`: 字段列表
            `main_source`: 主数据源对象
            `batch_size_hint`: 批次大小提示
            `name`: 模型名称
            `export_profile`: 导出元信息配置
        """
        # 转换 `sources` 为字典并检测重名
        sources_dict: Dict[str, SourceIr] = {}
        for source in sources:
            source_key = source.source_id
            if source_key in sources_dict:
                msg = f"数据源标识重复: {source_key!r}"
                raise ValueError(msg)
            sources_dict[source_key] = source

        # 转换 `fields` 为字典并检测重名
        fields_dict: Dict[str, SupportedFieldIr] = {}
        for field_spec in fields:
            if field_spec.field_id in fields_dict:
                msg = f"字段键名重复: {field_spec.field_id!r}"
                raise ValueError(msg)
            fields_dict[field_spec.field_id] = field_spec

        return cls(
            sources=sources_dict,
            fields=fields_dict,
            main_source=main_source,
            batch_size_hint=batch_size_hint,
            name=name,
            export_profile=export_profile,
            row_id_key=row_id_key,
        )

    def get_primary_field(self) -> Optional[FieldIr]:
        for field_spec in self.fields.values():
            if isinstance(field_spec, FieldIr) and field_spec.is_primary:
                return field_spec
        return None


__all__ = ()
