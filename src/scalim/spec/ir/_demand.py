from collections.abc import Mapping as MappingABC
from types import MappingProxyType
from typing import Any, Dict, List, Mapping, Optional, Sequence

from ...vendor.dataclassesx import dataclass, replace
from ._fields import FieldIr, SupportedFieldIr
from ._helpers import infer_lookup_steps
from ._sources import MainSourceIr, SourceIr
from .presentation import ExportProfileIr


@dataclass(frozen=True)
class DemandIr:
    """
    需求(IR): IR 层的顶层结构, 包含完整的数据需求定义, 包括数据源、字段、关系等
    """

    sources: Mapping[str, SourceIr]
    """
    数据源目录(`source_id` -> `SourceIr`);`SourceIr` 的 `SSOT`.

    运行时策略(`LookupChunking` / `SourceCache` / `RowsReuse`)只覆盖本目录.
    `FieldIr.source_id` / `LookupStepIr.to_source_id` 是图边身份,按 `id` 回这里解析.
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

        self._validate_source_graph_ids()

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

    def _validate_source_graph_ids(self) -> None:
        main_id = self.main_source.source_id
        if main_id in self.sources:
            msg = "主数据源 {!r} 不应出现在 sources 中".format(main_id)
            raise ValueError(msg)
        for field_key, field_spec in self.fields.items():
            if not isinstance(field_spec, FieldIr):
                continue
            source_id = field_spec.source_id
            if source_id != main_id and source_id not in self.sources:
                msg = "字段 {!r} 引用的数据源 {!r} 不存在".format(field_key, source_id)
                raise ValueError(msg)
            for step in field_spec.lookup_steps or ():
                if step.to_source_id not in self.sources:
                    msg = "字段 {!r} 的 lookup 引用数据源 {!r} 不存在".format(field_key, step.to_source_id)
                    raise ValueError(msg)

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

        # 转换 `fields` 为字典并检测重名;图边 `intern` 为 `source_id`
        fields_dict: Dict[str, SupportedFieldIr] = {}
        for field_spec in fields:
            interned = _intern_field(field_spec, sources_dict, main_source)
            if interned.field_id in fields_dict:
                msg = f"字段键名重复: {interned.field_id!r}"
                raise ValueError(msg)
            fields_dict[interned.field_id] = interned

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


def _intern_field(
    field_spec: SupportedFieldIr,
    sources_dict: Dict[str, SourceIr],
    main_source: MainSourceIr,
) -> SupportedFieldIr:
    if not isinstance(field_spec, FieldIr):
        return field_spec
    steps = field_spec.lookup_steps
    if steps is None and field_spec.relation is not None:
        to_source = sources_dict.get(field_spec.source_id)
        if to_source is not None:
            steps = infer_lookup_steps(field_spec.relation, main_source, to_source)
    if steps is field_spec.lookup_steps:
        return field_spec
    interned_steps = tuple(steps) if steps is not None else None
    return replace(field_spec, lookup_steps=interned_steps)


__all__ = ()
