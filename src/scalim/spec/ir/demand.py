from collections.abc import Sequence
from dataclasses import dataclass

from .fields import FieldIr, SupportedFieldIr
from .presentation import ExportProfileIr
from .sources import MainSourceIr, SourceIr


@dataclass(frozen=True)
class DemandIr:
    """
    需求(IR): IR 层的顶层结构, 包含完整的数据需求定义, 包括数据源、字段、关系等
    """

    sources: dict[str, SourceIr]
    """
    数据源字典 (source_name -> SourceDef),内部使用
    """

    fields: dict[str, SupportedFieldIr]
    """
    字段字典 (field_key -> FieldSpec | DerivedFieldSpec),内部使用
    """

    main_source: MainSourceIr
    """
    主数据源对象 (入口数据源)
    """

    row_id_key: str = "row_id"
    """
    内部行标识字段名 (框架维护)
    """

    batch_size_hint: int = 1000
    """
    建议的批次大小
    """

    name: str = ""
    """
    需求模型名称 (可选)
    """

    export_profile: ExportProfileIr | None = None
    """
    导出配置
    """

    def __post_init__(self) -> None:
        # 验证主数据源与 `sources` 无冲突
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

    @classmethod
    def from_irs(
        cls,
        sources: list[SourceIr],
        fields: Sequence[SupportedFieldIr],
        main_source: MainSourceIr,
        batch_size_hint: int = 1000,
        name: str = "",
        export_profile: ExportProfileIr | None = None,
        row_id_key: str = "row_id",
    ) -> "DemandIr":
        """从列表构造(推荐方式): 自动转换为字典并检测重名冲突

        参数：
            `sources`: 数据源列表
            `fields`: 字段列表
            `main_source`: 主数据源对象
            `batch_size_hint`: 批次大小提示
            `name`: 模型名称
            `export_profile`: 导出元信息配置
        """
        # 转换sources为字典并检测重名
        sources_dict: dict[str, SourceIr] = {}
        for source in sources:
            source_key = source.source_id
            if source_key in sources_dict:
                msg = f"数据源标识重复: {source_key!r}"
                raise ValueError(msg)
            sources_dict[source_key] = source

        # 转换fields为字典并检测重名
        fields_dict: dict[str, SupportedFieldIr] = {}
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

    def get_primary_field(self) -> FieldIr | None:
        for field_spec in self.fields.values():
            if isinstance(field_spec, FieldIr) and field_spec.is_primary:
                return field_spec
        return None
