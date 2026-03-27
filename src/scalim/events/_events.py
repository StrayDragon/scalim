# region imports

from typing import Any, Dict, Hashable, List, Optional, Tuple

from ..exceptions import safe_error_message, safe_error_type
from ..typedefs import RelationLookupResult
from ..vendor.dataclassesx import dataclass, field

# endregion


@dataclass(frozen=True)
class PipelineStartEvent:
    """管线开始事件.

    当管线开始执行时触发.
    """

    targets: List[str]
    """目标字段键列表."""

    batch_size: Optional[int]
    """配置的批处理大小(`None` 表示不分批)."""


@dataclass(frozen=True)
class PipelineEndEvent:
    """管线结束事件.

    当管线完成执行时触发.
    """

    total_batches: int
    """处理的批处理总数."""

    total_duration: float
    """总执行时间(秒)."""


@dataclass(frozen=True)
class BatchStartEvent:
    """批处理开始事件.

    当批处理开始处理时触发.
    """

    batch_num: int
    """批处理编号(从 1 开始)."""

    row_ids: List[Any]
    """此批次中的行标识列表."""


@dataclass(frozen=True)
class BatchEndEvent:
    """批处理结束事件.

    当批处理完成处理时触发.
    """

    batch_num: int
    """批处理编号(从 1 开始)."""

    duration: float
    """批处理耗时(秒)."""


@dataclass(frozen=True)
class LoaderCallEvent:
    """数据加载器调用事件.

    当数据加载器被调用时触发.
    """

    loader_name: str
    """加载器名称."""

    params: Dict[str, Any]
    """传递给加载器的参数."""

    result: Any
    """加载器返回的结果或摘要/样本."""

    duration: float
    """加载器执行耗时(秒)."""

    batch_num: Optional[int] = None
    """批次编号(可选)."""

    cache_status: Optional[str] = None
    """缓存命中状态(`hit`/`miss`,可选)."""

    cache_scope: Optional[str] = None
    """缓存作用域(例如 `batch`,可选)."""

    lookup_key_count: Optional[int] = None
    """本次调用的查找键数量(可选)."""

    field_keys: Optional[List[str]] = None
    """加载器关联字段键列表(可选)."""


@dataclass(frozen=True)
class LoaderRetryEvent:
    """加载重试事件.

    当一次加载调用失败且框架决定重试时触发(在进入等待休眠之前).
    """

    loader_name: str
    """加载器名称."""

    callsite: str
    """调用点标识(用于定位触发位置)."""

    attempt_num: int
    """当前重试次数(从 1 开始)."""

    max_attempts: int
    """最大尝试次数上限."""

    elapsed_seconds: float
    """已消耗的累计时间(秒,包含等待)."""

    sleep_seconds: float
    """本次重试前的等待时间(秒)."""

    error_type: str
    """异常类型名称."""

    error_message: Optional[str] = None
    """异常信息(可选)."""

    batch_num: Optional[int] = None
    """批次编号(可选)."""


@dataclass(frozen=True)
class FieldComputeEvent:
    """字段计算事件.

    当派生字段被计算时触发.
    """

    field_key: str
    """字段键."""

    row_id: Optional[Hashable]
    """行标识."""

    dependencies: Dict[str, Any]
    """依赖字段值映射."""

    result: Any
    """计算结果."""


@dataclass(frozen=True)
class ErrorEvent:
    """错误事件.

    当执行过程中发生错误时触发.
    """

    error: Exception
    """发生的异常对象."""

    context: Dict[str, Any]
    """额外的上下文信息."""

    error_type: str = field(init=False)
    """异常类型名称(稳定字段)."""

    error_message: Optional[str] = field(init=False)
    """安全的异常信息(稳定字段,默认脱敏)."""

    def __post_init__(self) -> None:
        # 冻结数据类:使用 `object.__setattr__` 填充派生字段.
        object.__setattr__(self, "error_type", safe_error_type(self.error))
        object.__setattr__(self, "error_message", safe_error_message(self.error))


@dataclass(frozen=True)
class DiagnosticWarningEvent:
    """诊断告警事件.

    用于记录非阻断性问题,提示用户检查数据或配置.
    """

    message: str
    """可读的告警说明."""

    source_id: Optional[str]
    """关联的目标数据源标识."""

    field_id: Optional[str]
    """当前计算字段标识."""

    lookup_key: Any
    """外键值/关联键."""

    row_id: Optional[Hashable]
    """行标识(可选)."""


@dataclass(frozen=True)
class FieldSlimEvent:
    """字段瘦身事件(FR022)."""

    field_key: str
    """字段键."""

    reason: str
    """触发原因标识."""

    batch_num: Optional[int]
    """批次编号(可选)."""

    remaining_fields: Optional[int]
    """瘦身后保留的字段数量."""


@dataclass(frozen=True)
class RowWriteEvent:
    """行写入事件(FR023)."""

    row_id: Hashable
    """行标识."""

    field_count: int
    """写入的字段数量."""

    batch_num: Optional[int]
    """批次编号(可选)."""

    row_index: Optional[int]
    """批次内行序号(从 0 开始)."""


@dataclass(frozen=True)
class RowReleaseEvent:
    """行内存释放事件(FR023)."""

    row_id: Hashable
    """行标识."""

    released_fields: List[str]
    """已释放的字段键列表."""

    retained_fields: List[str]
    """仍保留的字段键列表."""

    batch_num: Optional[int]
    """批次编号(可选)."""


@dataclass(frozen=True)
class LoaderSlimEvent:
    """加载器结果瘦身事件(FR022)."""

    loader_name: str
    """加载器名称."""

    original_keys: int
    """瘦身前的键数量."""

    extracted_fields: List[str]
    """被抽取/保留的字段键列表."""

    batch_num: Optional[int]
    """批次编号(可选)."""


@dataclass(frozen=True)
class ColumnWriteEvent:
    """列写入事件(FR023)."""

    field_key: str
    """字段键."""

    row_count: int
    """写入的行数."""

    batch_num: int
    """批次编号."""


@dataclass(frozen=True)
class RelationLookupEvent:
    """关联查找事件."""

    field_key: str
    """当前字段键."""

    row_id: Hashable
    """行标识."""

    fk_raw: Any
    """原始外键值."""

    fk_normalized: Any
    """归一化后的外键值."""

    target_source: str
    """目标数据源标识."""

    result: RelationLookupResult
    """关联查找结果类型."""

    fk_type: Optional[str] = None
    """原始外键类型名称(可选)."""

    expected_type: Optional[str] = None
    """期望的外键类型名称(可选)."""

    error_message: Optional[str] = None
    """错误说明(可选)."""


@dataclass(frozen=True)
class StageSpanEvent:
    """阶段耗时事件(`loader`/`compute`/`write`)."""

    stage: str
    """阶段名称(例如 `loader`/`compute`/`write`)."""

    batch_num: int
    """批次编号."""

    duration: float
    """阶段耗时(秒)."""


@dataclass(frozen=True)
class OutputTargetEndEvent:
    """输出目标结束统计事件.

    由输出组合层在 `close()` 时发出,用于记录每个输出目标的写出统计.
    """

    target_id: str
    """输出目标标识."""

    output_path: Optional[str]
    """输出路径(可选;例如工作簿路径或文件路径)."""

    sheet_name: Optional[str]
    """`Excel` 工作表名称(可选)."""

    row_count: int
    """写入的行数."""

    error_count: int
    """写入/关闭过程的错误次数."""

    duration: float
    """该输出目标累计耗时(秒)."""

    disabled: bool
    """是否被禁用(例如 `failure_policy=primary_only` 下发生错误后被禁用)."""

    error_type: Optional[str] = None
    """首个错误的异常类型(可选)."""

    error_message: Optional[str] = None
    """首个错误的异常消息(可选)."""


@dataclass(frozen=True)
class AdaptiveSchedulerDecisionEvent:
    """自适应调度器决策事件.

    仅在 `parallel_mode=\"adaptive\"` 且已订阅此事件时触发(按需启用).
    """

    batch_num: int
    """批次编号."""

    layer_index: int
    """当前调度层序号(从 0 开始)."""

    decision: str
    """决策结果标识."""

    backend: str
    """执行后端标识."""

    reason: Optional[str] = None
    """决策原因说明(可选)."""

    layer_task_count: Optional[int] = None
    """当前层任务数量(可选)."""

    process_failure_mode: Optional[str] = None
    """进程后端失败处理模式(可选)."""

    pool_limits: Optional[Dict[str, int]] = None
    """执行器池容量限制映射(可选)."""

    pool_wait_ms_total: Optional[Dict[str, float]] = None
    """按池统计的等待总时长(毫秒,可选)."""

    pool_wait_ms_max: Optional[Dict[str, float]] = None
    """按池统计的单次等待最大时长(毫秒,可选)."""

    pool_wait_count: Optional[Dict[str, int]] = None
    """按池统计的等待次数(可选)."""


@dataclass(frozen=True)
class WorkflowNodeStartEvent:
    """工作流节点开始事件.

    该事件用于表达工作流编排层已调度/开始执行某个节点.
    """

    workflow_exec_id: str
    """`workflow_exec_id`: 工作流执行标识(一次调用内稳定)."""

    workflow_node_id: str
    """`workflow_node_id`: 工作流节点稳定 `id`(对 `demand` 节点等于工作流 `YAML` 的 `runs[*].id`)."""

    node_type: str
    """节点类型(例如 `demand`)."""

    demand_path: Optional[str] = None
    """当 `node_type=demand` 时,对应的 `demand` `YAML` 路径(可选)."""


@dataclass(frozen=True)
class WorkflowNodeEndEvent:
    """工作流节点结束事件.

    该事件用于表达工作流编排层已完成某个节点的执行(成功或失败).
    """

    workflow_exec_id: str
    """`workflow_exec_id`: 工作流执行标识(一次调用内稳定)."""

    workflow_node_id: str
    """`workflow_node_id`: 工作流节点稳定 `id`(对 `demand` 节点等于工作流 `YAML` 的 `runs[*].id`)."""

    node_type: str
    """节点类型(例如 `demand`)."""

    status: str
    """结束状态(例如 `ok`/`error`)."""

    demand_path: Optional[str] = None
    """当 `node_type=demand` 时,对应的 `demand` `YAML` 路径(可选)."""

    error_type: Optional[str] = None
    """失败时的异常类型(可选)."""

    error_message: Optional[str] = None
    """失败时的异常消息(可选)."""


@dataclass(frozen=True)
class WorkflowNodeCancelledEvent:
    """工作流节点取消事件.

    该事件用于表达工作流编排层决定取消某个节点的执行(例如因失败策略取消未开始节点).
    """

    workflow_exec_id: str
    """`workflow_exec_id`: 工作流执行标识(一次调用内稳定)."""

    workflow_node_id: str
    """`workflow_node_id`: 工作流节点稳定 `id`(对 `demand` 节点等于工作流 `YAML` 的 `runs[*].id`)."""

    node_type: str
    """节点类型(例如 `demand`)."""

    reason: str
    """取消原因标识(例如 `dependency_failed` / `upstream_cancelled` / `policy_all_fail`)."""

    message: str
    """可读的诊断说明(用于排障)."""

    demand_path: Optional[str] = None
    """当 `node_type=demand` 时,对应的 `demand` `YAML` 路径(可选)."""


@dataclass(frozen=True)
class WorkflowCacheAcquireEvent:
    """工作流缓存 `acquire` 事件.

    用于表达某个工作流节点获取(`acquire`)了一个 `cache pool` 条目.
    """

    workflow_exec_id: str
    workflow_node_id: str
    cache_kind: str
    source_id: str
    signature_digest: str
    cache_status: str
    conflict_policy: str
    conflict_detected: bool = False
    conflict_diff_fields: Tuple[str, ...] = ()
    conflict_target_signature_digest: Optional[str] = None


@dataclass(frozen=True)
class WorkflowCacheReleaseEvent:
    """工作流缓存 `release` 事件.

    用于表达某个工作流节点释放(`release`)了其持有的 `cache pool` 条目引用.
    """

    workflow_exec_id: str
    workflow_node_id: str
    cache_kind: str
    source_id: str
    signature_digest: str
    remaining_consumers: int
    release_policy: str
    is_pinned: bool = False


@dataclass(frozen=True)
class WorkflowCacheEvictEvent:
    """工作流缓存 `evict` 事件.

    用于表达 `cache pool` 中的某个条目被淘汰/释放.
    """

    workflow_exec_id: str
    workflow_node_id: str
    cache_kind: str
    source_id: str
    signature_digest: str
    reason: str


@dataclass(frozen=True)
class WorkflowResourceCreateEvent:
    """工作流资源 `create` 事件.

    用于表达工作流级共享资源(例如 `workbook`/`csv`/`sheetbook`)被创建/初始化.
    """

    workflow_exec_id: str
    workflow_node_id: str
    resource_type: str
    resource_id: str
    path: str


@dataclass(frozen=True)
class WorkflowResourceWriteEvent:
    """工作流资源 `write` 事件.

    用于表达某个 `workflow node` 对共享资源执行了一次写入意图.
    """

    workflow_exec_id: str
    workflow_node_id: str
    resource_type: str
    resource_id: str
    path: str
    write_kind: str
    action: str
    input_node_id: Optional[str] = None
    input_output_id: Optional[str] = None
    sheet: Optional[str] = None


@dataclass(frozen=True)
class WorkflowResourceCommitEvent:
    """工作流资源 `commit` 事件.

    用于表达 `workflow` 成功结束时共享资源的原子落盘.
    """

    workflow_exec_id: str
    workflow_node_id: str
    resource_type: str
    resource_id: str
    path: str


@dataclass(frozen=True)
class WorkflowResourceDiscardEvent:
    """工作流资源 `discard` 事件.

    用于表达 `workflow` 失败结束时共享资源被丢弃(不产生部分提交的最终文件).
    """

    workflow_exec_id: str
    workflow_node_id: str
    resource_type: str
    resource_id: str
    path: str
    reason: str


__all__ = []
