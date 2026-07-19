from typing import Any, List, Union

from .....vendor.compact.typing_extensionsx import TypedDict


class PerformanceReportRaw(TypedDict, total=False):
    format: str
    output: str
    include_details: bool


class PerformanceThresholdsRaw(TypedDict, total=False):
    batch_duration_warn: float
    memory_increase_warn: float


class PerformanceRaw(TypedDict, total=False):
    enabled: bool
    metrics: Union[List[str], str]
    sampling_interval: int
    report: PerformanceReportRaw
    thresholds: PerformanceThresholdsRaw


class RelationReportRaw(TypedDict, total=False):
    format: str
    output: str


class RelationsRaw(TypedDict, total=False):
    enabled: bool
    sampling_rate: float
    log_type_mismatch: bool
    max_samples: int
    report: RelationReportRaw


class LoggingRaw(TypedDict, total=False):
    enabled: bool
    renderer: str


class TraceRaw(TypedDict, total=False):
    enabled: bool


class RowGapRaw(TypedDict, total=False):
    enabled: bool
    primary_loader_name: str
    data_loader_names: Union[List[str], str]
    sample_limit: int


class MemoryOptimizationRaw(TypedDict, total=False):
    enabled: bool
    auto_report: bool
    max_fields: int


class VizRaw(TypedDict, total=False):
    enabled: bool
    output_dir: str
    output_path: str
    snapshot_path: str
    payload_policy: str
    sample_size: int
    run_name: str
    env: str
    use_default_output_dir: bool


class ObservabilityRaw(TypedDict, total=False):
    logging: LoggingRaw
    performance: PerformanceRaw
    relations: RelationsRaw
    viz: VizRaw
    trace: TraceRaw
    row_gap: RowGapRaw
    memory_opt: MemoryOptimizationRaw


class GuardrailsLoaderRaw(TypedDict, total=False):
    validate_result: bool
    required_fields: List[Any]
    on_transform_error: str


class GuardrailsRelationsRaw(TypedDict, total=False):
    null_key_max_rate: float
    type_error_max_rate: float


class GuardrailsComputeRaw(TypedDict, total=False):
    on_error: str


class GuardrailsRaw(TypedDict, total=False):
    enabled: bool
    mode: str
    loader: GuardrailsLoaderRaw
    relations: GuardrailsRelationsRaw
    compute: GuardrailsComputeRaw


class LoaderRetryRaw(TypedDict, total=False):
    enabled: bool
    should_retry: str
    max_attempts: int
    max_elapsed_seconds: float
    backoff: str
    base_delay_seconds: float
    max_delay_seconds: float
    jitter: bool


__all__ = ()
