"""Scalim `demo_big_data_report` notebooks shared fixtures/oracle/helpers.

说明:
- 教学主流程与可运行 SSOT 位于 `notebooks/marimo/demo_big_data_report/`
- 本包仅保留可复用的 fixture 数据/loader、oracle/verification 与少量工具函数
"""

from .loaders import ECommerceConfig, get_config, set_config
from .shared import TARGET_FIELDS_FULL, build_ecommerce_model, build_ecommerce_runtime_bindings

__all__ = [
    "TARGET_FIELDS_FULL",
    "ECommerceConfig",
    "build_ecommerce_model",
    "build_ecommerce_runtime_bindings",
    "get_config",
    "set_config",
]
