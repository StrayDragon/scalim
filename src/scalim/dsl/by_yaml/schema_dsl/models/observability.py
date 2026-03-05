# pyright: reportPrivateUsage=false

from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import ClassVar, Optional, Tuple

from ..constants import (
    DEFAULT_PERF_REPORT_FORMAT,
    DEFAULT_PERF_SAMPLING_INTERVAL,
    DEFAULT_REL_LOG_TYPE_MISMATCH,
    DEFAULT_REL_REPORT_FORMAT,
    DEFAULT_RELATION_MAX_SAMPLES,
    DEFAULT_RELATION_SAMPLING_RATE,
    _schema_meta,
)


@dataclass(frozen=True)
class PerformanceThresholdsConfig:
    SCHEMA_NAME: ClassVar[str] = "performance_thresholds"
    """性能阈值配置对象在 `YAML` 中的节点名称."""

    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    """是否允许出现未声明的额外键."""

    batch_duration_warn: Optional[float] = dataclass_field(
        default=None,
        metadata=_schema_meta(desc="批次耗时告警阈值(秒)"),
    )
    """批次耗时告警阈值(秒,可选)."""

    memory_increase_warn: Optional[float] = dataclass_field(
        default=None,
        metadata=_schema_meta(desc="内存增长告警阈值(MB)"),
    )
    """内存增长告警阈值(兆字节,可选)."""


@dataclass(frozen=True)
class PerformanceReportConfig:
    SCHEMA_NAME: ClassVar[str] = "performance_report"
    """性能报告输出配置对象在 `YAML` 中的节点名称."""

    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    """是否允许出现未声明的额外键."""

    format: str = dataclass_field(
        default=DEFAULT_PERF_REPORT_FORMAT,
        metadata=_schema_meta(
            desc="报告输出格式",
            md=("报告输出格式.\n\n- `console`: 控制台输出\n- `json`: JSON 文件\n- `csv`: CSV 文件\n- `none`: 不输出报告"),
            choices=["console", "json", "csv", "none"],
            default=DEFAULT_PERF_REPORT_FORMAT,
            examples=["console"],
        ),
    )
    """报告输出格式:`console`/`json`/`csv`/`none`."""

    output: Optional[str] = dataclass_field(default=None, metadata=_schema_meta(desc="报告输出路径"))
    """报告输出路径(可选)."""

    include_details: bool = dataclass_field(
        default=False,
        metadata=_schema_meta(desc="包含详细统计", md="包含详细统计.", default=False),
    )
    """是否包含详细统计."""


@dataclass(frozen=True)
class PerformanceConfig:
    SCHEMA_NAME: ClassVar[str] = "performance"
    """性能可观测性配置对象在 `YAML` 中的节点名称."""

    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    """是否允许出现未声明的额外键."""

    enabled: bool = dataclass_field(
        default=False,
        metadata=_schema_meta(desc="启用性能监控", md="启用性能监控.", default=False),
    )
    """是否启用性能监控."""

    metrics: Tuple[str, ...] = dataclass_field(
        default=("duration",),
        metadata=_schema_meta(
            desc="要收集的指标类型 (duration/memory/cpu)",
            md="要收集的指标类型.\n\n- 可选: duration / memory / cpu",
            items_choices=["duration", "memory", "cpu"],
        ),
    )
    """要收集的指标类型列表(例如 `duration`/`memory`/`cpu`)."""

    sampling_interval: int = dataclass_field(
        default=DEFAULT_PERF_SAMPLING_INTERVAL,
        metadata=_schema_meta(
            desc="资源采样间隔(批次数)",
            md="资源采样间隔(按批次计).",
            min=1,
            default=DEFAULT_PERF_SAMPLING_INTERVAL,
        ),
    )
    """资源采样间隔(按批次数)."""

    report: Optional[PerformanceReportConfig] = dataclass_field(
        default=None,
        metadata=_schema_meta(ref="performance_report"),
    )
    """性能报告输出配置(可选)."""

    thresholds: Optional[PerformanceThresholdsConfig] = dataclass_field(
        default=None,
        metadata=_schema_meta(ref="performance_thresholds"),
    )
    """性能告警阈值配置(可选)."""


@dataclass(frozen=True)
class RelationReportConfig:
    SCHEMA_NAME: ClassVar[str] = "relation_report"
    """关联报告输出配置对象在 `YAML` 中的节点名称."""

    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    """是否允许出现未声明的额外键."""

    format: str = dataclass_field(
        default=DEFAULT_REL_REPORT_FORMAT,
        metadata=_schema_meta(
            desc="报告输出格式",
            md=("报告输出格式.\n\n- `console`: 控制台输出\n- `json`: JSON 文件\n- `none`: 不输出报告"),
            choices=["console", "json", "none"],
            default=DEFAULT_REL_REPORT_FORMAT,
            examples=["console"],
        ),
    )
    """报告输出格式:`console`/`json`/`none`."""

    output: Optional[str] = dataclass_field(default=None, metadata=_schema_meta(desc="报告输出路径"))
    """报告输出路径(可选)."""


@dataclass(frozen=True)
class RelationsConfig:
    SCHEMA_NAME: ClassVar[str] = "relations"
    """关联可观测性配置对象在 `YAML` 中的节点名称."""

    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    """是否允许出现未声明的额外键."""

    enabled: bool = dataclass_field(
        default=False,
        metadata=_schema_meta(desc="启用关联可观测性", md="启用关联可观测性.", default=False),
    )
    """是否启用关联可观测性."""

    sampling_rate: float = dataclass_field(
        default=DEFAULT_RELATION_SAMPLING_RATE,
        metadata=_schema_meta(
            desc="采样率(0.0-1.0)",
            md="采样率(0.0-1.0).",
            min=0.0,
            max=1.0,
            default=DEFAULT_RELATION_SAMPLING_RATE,
        ),
    )
    """采样率(0.0-1.0)."""

    log_type_mismatch: bool = dataclass_field(
        default=DEFAULT_REL_LOG_TYPE_MISMATCH,
        metadata=_schema_meta(desc="记录类型不匹配日志", md="记录类型不匹配日志.", default=DEFAULT_REL_LOG_TYPE_MISMATCH),
    )
    """是否记录类型不匹配日志."""

    max_samples: int = dataclass_field(
        default=DEFAULT_RELATION_MAX_SAMPLES,
        metadata=_schema_meta(
            desc="最大采样数量",
            md="最大采样数量.",
            min=0,
            default=DEFAULT_RELATION_MAX_SAMPLES,
        ),
    )
    """最大采样数量."""

    report: Optional[RelationReportConfig] = dataclass_field(
        default=None,
        metadata=_schema_meta(ref="relation_report"),
    )
    """关联报告输出配置(可选)."""


@dataclass(frozen=True)
class VizConfig:
    SCHEMA_NAME: ClassVar[str] = "viz"
    """可视化输出配置对象在 `YAML` 中的节点名称."""

    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    """是否允许出现未声明的额外键."""

    enabled: bool = dataclass_field(
        default=False,
        metadata=_schema_meta(desc="启用 Scalim Viz 输出", md="启用 Scalim Viz 输出.", default=False),
    )
    """是否启用 `Scalim Viz` 输出."""

    output_dir: Optional[str] = dataclass_field(
        default=None,
        metadata=_schema_meta(
            desc="输出目录(自动追加 scalim-viz)",
            md=(
                "输出目录(自动追加 scalim-viz).\n\n"
                "- 写入路径: output_dir/scalim-viz/<run_id>/viz_*.json\n"
                "- 若 output_dir 已包含 scalim-viz,则直接使用\n"
                "- 若显式配置 output_path/snapshot_path,则忽略该规则"
            ),
        ),
    )
    """输出目录(会自动追加 `scalim-viz`,可选)."""

    output_path: Optional[str] = dataclass_field(
        default=None,
        metadata=_schema_meta(desc="事件输出文件路径(可选)", md="事件输出文件路径(可选)."),
    )
    """事件输出文件路径(可选)."""

    snapshot_path: Optional[str] = dataclass_field(
        default=None,
        metadata=_schema_meta(desc="快照输出文件路径(可选)", md="快照输出文件路径(可选)."),
    )
    """快照输出文件路径(可选)."""

    append: bool = dataclass_field(
        default=False,
        metadata=_schema_meta(
            desc="事件文件追加写入",
            md=(
                "事件文件追加写入(可选).\n\n"
                "- 默认 `false`: 每次运行会覆盖 `output_path` 对应文件,避免跨 run 混写\n"
                "- 设为 `true` 时,将以 JSONL 追加写入(旧行为)\n"
                "- `output_dir` 写入到按 run 隔离目录时,通常不需要开启"
            ),
            default=False,
            examples=[False],
        ),
    )
    """是否以 `JSONL` 追加写入事件文件."""

    trace_enabled: bool = dataclass_field(
        default=False,
        metadata=_schema_meta(
            desc="启用高频 trace 输出",
            md=(
                "启用高频 trace 输出(可选).\n\n"
                "- `false`(默认): 仅输出编排级事件到 `viz_events.jsonl`\n"
                "- `true`: 额外输出高频 trace 事件到 `viz_trace.jsonl`(例如 field/row/relation lookup)\n\n"
                "建议: 默认关闭;需要深挖时在 UI 勾选加载 trace 并配合过滤/步进 lens 使用.\n\n"
                "旧字段 `observability.viz.event_mode` 已移除,请使用 `trace_enabled`."
            ),
            default=False,
            examples=[False],
        ),
    )
    """是否启用高频 `trace` 事件输出."""

    payload_policy: str = dataclass_field(
        default="summary",
        metadata=_schema_meta(
            desc="事件 payload 策略",
            md=("事件 payload 策略.\n\n- `none`: 不输出 payload\n- `summary`: 仅摘要\n- `sample`: 抽样\n- `full`: 全量"),
            choices=["none", "summary", "sample", "full"],
            default="summary",
            examples=["summary"],
        ),
    )
    """事件负载策略:`none`/`summary`/`sample`/`full`."""

    sample_size: int = dataclass_field(
        default=5,
        metadata=_schema_meta(
            desc="sample 策略下的样本数量",
            md="sample 策略下的样本数量.",
            min=0,
            default=5,
        ),
    )
    """在 `sample` 策略下的样本数量."""

    run_name: Optional[str] = dataclass_field(
        default=None,
        metadata=_schema_meta(desc="运行名称", md="运行名称(可选)."),
    )
    """运行名称(可选)."""

    env: Optional[str] = dataclass_field(
        default=None,
        metadata=_schema_meta(desc="运行环境标签", md="运行环境标签(可选)."),
    )
    """运行环境标签(可选)."""

    use_default_output_dir: bool = dataclass_field(
        default=False,
        metadata=_schema_meta(desc="使用默认输出目录", md="使用默认输出目录(~/.config/scalim-viz 等).", default=False),
    )
    """是否使用默认输出目录(例如 `~/.config/scalim-viz`)."""


@dataclass(frozen=True)
class LoggingConfig:
    SCHEMA_NAME: ClassVar[str] = "logging"
    """日志观测配置对象在 `YAML` 中的节点名称."""

    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    """是否允许出现未声明的额外键."""

    enabled: bool = dataclass_field(
        default=True,
        metadata=_schema_meta(desc="启用日志观测", md="启用日志观测.", default=True),
    )
    """是否启用日志观测."""

    renderer: str = dataclass_field(
        default="pretty",
        metadata=_schema_meta(
            desc="日志渲染器(pretty/logger)",
            md="日志渲染器.\n\n- `pretty`: 输出到 pretty console(如 panel/table)\n- `logger`: 输出到标准 logger",
            choices=["pretty", "logger"],
            default="pretty",
            examples=["pretty"],
        ),
    )
    """日志渲染器:`pretty` 或 `logger`."""


@dataclass(frozen=True)
class TraceConfig:
    SCHEMA_NAME: ClassVar[str] = "trace"
    """执行追踪配置对象在 `YAML` 中的节点名称."""

    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    """是否允许出现未声明的额外键."""

    enabled: bool = dataclass_field(
        default=False,
        metadata=_schema_meta(desc="启用执行追踪", md="启用执行追踪.", default=False),
    )
    """是否启用执行追踪."""


@dataclass(frozen=True)
class RowGapConfig:
    SCHEMA_NAME: ClassVar[str] = "row_gap"
    """行缺口统计配置对象在 `YAML` 中的节点名称."""

    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    """是否允许出现未声明的额外键."""

    enabled: bool = dataclass_field(
        default=False,
        metadata=_schema_meta(desc="启用行缺口统计", md="启用行缺口统计.", default=False),
    )
    """是否启用行缺口统计."""

    primary_loader_name: str = dataclass_field(
        default="primary_keys",
        metadata=_schema_meta(desc="主数据 loader 名称", md="主数据 loader 名称.", default="primary_keys"),
    )
    """主数据加载器名称."""

    data_loader_names: Tuple[str, ...] = dataclass_field(
        default=("base_info",),
        metadata=_schema_meta(
            desc="参与统计的 loader 列表",
            md="参与统计的 loader 列表.",
            items={"type": "string"},
        ),
    )
    """参与统计的加载器名称列表."""

    sample_limit: int = dataclass_field(
        default=5,
        metadata=_schema_meta(desc="缺口采样数量", md="缺口采样数量.", min=0, default=5),
    )
    """缺口采样数量上限."""


@dataclass(frozen=True)
class MemoryOptimizationConfig:
    SCHEMA_NAME: ClassVar[str] = "memory_opt"
    """内存优化统计配置对象在 `YAML` 中的节点名称."""

    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    """是否允许出现未声明的额外键."""

    enabled: bool = dataclass_field(
        default=False,
        metadata=_schema_meta(desc="启用内存优化统计", md="启用内存优化统计.", default=False),
    )
    """是否启用内存优化统计."""

    auto_report: bool = dataclass_field(
        default=False,
        metadata=_schema_meta(desc="自动输出摘要", md="自动输出摘要.", default=False),
    )
    """是否自动输出摘要."""

    max_fields: int = dataclass_field(
        default=0,
        metadata=_schema_meta(desc="摘要字段上限", md="摘要字段上限(0 表示不限制).", min=0, default=0),
    )
    """摘要字段上限(`0` 表示不限制)."""


@dataclass(frozen=True)
class ObservabilityConfig:
    SCHEMA_NAME: ClassVar[str] = "observability"
    """可观测性配置对象在 `YAML` 中的节点名称."""

    SCHEMA_ADDITIONAL_PROPERTIES: ClassVar[bool] = False
    """是否允许出现未声明的额外键."""

    logging: Optional[LoggingConfig] = dataclass_field(
        default=None,
        metadata=_schema_meta(
            desc="日志观测配置",
            md="日志观测配置.\n\n- 控制日志输出开启/关闭",
            ref="logging",
        ),
    )
    """日志观测配置(可选)."""

    performance: Optional[PerformanceConfig] = dataclass_field(
        default=None,
        metadata=_schema_meta(
            desc="性能可观测性配置",
            md="性能可观测性配置.\n\n- 关注耗时/内存/CPU 等指标",
            ref="performance",
        ),
    )
    """性能可观测性配置(可选)."""

    relations: Optional[RelationsConfig] = dataclass_field(
        default=None,
        metadata=_schema_meta(
            desc="关联可观测性配置",
            md="关联可观测性配置.\n\n- 关注关联步骤的采样与类型校验",
            ref="relations",
        ),
    )
    """关联可观测性配置(可选)."""

    viz: Optional[VizConfig] = dataclass_field(
        default=None,
        metadata=_schema_meta(
            desc="Scalim Viz 可视化输出配置",
            md="Scalim Viz 可视化输出配置.\n\n- 输出 viz_snapshot.json + viz_events.jsonl",
            ref="viz",
        ),
    )
    """可视化输出配置(可选)."""

    trace: Optional[TraceConfig] = dataclass_field(
        default=None,
        metadata=_schema_meta(
            desc="执行追踪配置",
            md="执行追踪配置.\n\n- 记录批次级执行步骤",
            ref="trace",
        ),
    )
    """执行追踪配置(可选)."""

    row_gap: Optional[RowGapConfig] = dataclass_field(
        default=None,
        metadata=_schema_meta(
            desc="行缺口统计配置",
            md="行缺口统计配置.\n\n- 统计 loader 期望/实际行数差异",
            ref="row_gap",
        ),
    )
    """行缺口统计配置(可选)."""

    memory_opt: Optional[MemoryOptimizationConfig] = dataclass_field(
        default=None,
        metadata=_schema_meta(
            desc="内存优化统计配置",
            md="内存优化统计配置.\n\n- 汇总字段瘦身/行释放等事件",
            ref="memory_opt",
        ),
    )
    """内存优化统计配置(可选)."""
