import threading
from contextlib import contextmanager
from typing import Iterator

from scalim_misc.demo_big_data_report.loaders import ECommerceConfig, get_config, set_config

_ECOMMERCE_CONFIG_LOCK = threading.Lock()


@contextmanager
def patched_ecommerce_config(config: ECommerceConfig) -> Iterator[ECommerceConfig]:
    """临时替换 `demo_big_data_report` 的全局配置.

    说明:
    - `scalim_misc.demo_big_data_report.loaders` 使用模块级全局配置(`set_config/get_config`),在并行执行的测试环境中可能产生隐式耦合。
    - 该上下文管理器提供集中化的 patch/restore,并通过进程内锁避免未来线程并行执行器下的竞态。

    注意:
    - 该锁仅保证“单进程内”的互斥;在 `pytest-xdist` 的多进程模型下,每个 worker 进程拥有独立全局状态。
    """
    with _ECOMMERCE_CONFIG_LOCK:
        prev = get_config()
        set_config(config)
        try:
            yield config
        finally:
            set_config(prev)


__all__ = ("patched_ecommerce_config",)
