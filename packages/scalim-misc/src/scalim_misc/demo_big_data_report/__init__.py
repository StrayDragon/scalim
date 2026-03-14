"""Scalim `demo_big_data_report` 教程与集成对拍模块.

此包承载可复用的“章节实现/对拍/对照组验证/示例数据加载器”,供:
- `notebooks/marimo/demo_big_data_report/demo_main.py` (交互教程)
- `notebooks/marimo/run_examples.py` (`just examples` 对拍 gate)
- `tests/` (复用同一套示例用例与验证逻辑)
"""

from .loaders import ECommerceConfig, get_config, set_config
from .shared import TARGET_FIELDS_FULL, build_ecommerce_model

__all__ = [
    "TARGET_FIELDS_FULL",
    "ECommerceConfig",
    "build_ecommerce_model",
    "get_config",
    "set_config",
]
