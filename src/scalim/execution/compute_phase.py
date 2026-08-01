"""派生字段计算阶段标注(`FIELD_COMPUTE` 事件 `meta`).

单独成模块以避免 `compute` 算子与 `write-precompute` 之间的循环导入.
"""

COMPUTE_PHASE_META_KEY = "scalim_compute_phase"
"""事件 `meta` 中标注计算阶段的稳定键名."""

COMPUTE_PHASE_OPERATOR = "operator"
"""在 `compute` 算子段完成的计算."""

COMPUTE_PHASE_WRITE_PRECOMPUTE = "write_precompute"
"""在写出前(行写出 / 列写出)延迟物化的计算."""


__all__ = (
    "COMPUTE_PHASE_META_KEY",
    "COMPUTE_PHASE_OPERATOR",
    "COMPUTE_PHASE_WRITE_PRECOMPUTE",
)
