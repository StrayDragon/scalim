import pytest

from scalim_misc.demo_big_data_report.loaders import ECommerceConfig, get_config

from .demo_big_data_report_config import patched_ecommerce_config


def test_patched_ecommerce_config_restores_on_exception() -> None:
    prev = get_config()
    cfg = ECommerceConfig(order_count=1)

    with pytest.raises(RuntimeError, match="boom"):
        with patched_ecommerce_config(cfg):
            assert get_config() == cfg
            raise RuntimeError("boom")

    assert get_config() == prev
