from contextlib import contextmanager
from typing import Iterator, List, Optional, Sequence, Tuple

from scalim.typedefs import RowData


def load_orders_small(limit: int = 20) -> List[RowData]:
    from scalim_misc.demo_big_data_report.loaders import load_orders

    return list(load_orders())[: int(limit)]


def verify_ecommerce_results(results: Sequence[RowData], *, fields_to_check: Sequence[str]) -> Tuple[bool, str]:
    from scalim_misc.demo_big_data_report.verification import verify_scalim_output

    verification = verify_scalim_output(list(results), fields_to_check=list(fields_to_check))
    return bool(verification.passed), str(verification.summary)


@contextmanager
def ecommerce_small_config_guard() -> Iterator[None]:
    from scalim_misc.demo_big_data_report.loaders import ECommerceConfig
    from tests.support.demo_big_data_report_config import patched_ecommerce_config

    cfg = ECommerceConfig(
        order_count=30,
        customer_count=10,
        product_count=10,
        category_count=5,
        warehouse_count=5,
        region_count=5,
        promotion_count=5,
        payment_method_count=3,
        logistics_count=3,
    )
    with patched_ecommerce_config(cfg):
        yield


def build_ecommerce_model_small() -> "object":
    from scalim_misc.demo_big_data_report.shared import build_ecommerce_model

    with ecommerce_small_config_guard():
        return build_ecommerce_model()


__all__ = [
    "build_ecommerce_model_small",
    "ecommerce_small_config_guard",
    "load_orders_small",
    "verify_ecommerce_results",
]
