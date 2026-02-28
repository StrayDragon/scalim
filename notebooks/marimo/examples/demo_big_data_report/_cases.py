"""`demo_big_data_report` 的用例注册表。

集中管理演示场景的配置与执行方式，以便：
- 测试复用同一套场景定义（避免重复写 `config`/`targets`/`verification` 的组装逻辑）
- 演示维持“用例是什么”的单一事实来源

同时兼容两种导入方式：
- 包导入：`notebooks.marimo.examples.demo_big_data_report._cases`
- 目录脚本式导入：运行本目录文件时通过 `sys.path` 注入
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    from ._loaders import ECommerceConfig, get_config, load_orders, set_config
    from ._shared import build_ecommerce_model
    from ._verification import VerificationResult, verify_scalim_output
except ImportError:
    from _loaders import ECommerceConfig, get_config, load_orders, set_config
    from _shared import build_ecommerce_model
    from _verification import VerificationResult, verify_scalim_output


@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    config: ECommerceConfig
    targets: Tuple[str, ...]
    row_limit: int = 20


def build_test_config_small() -> ECommerceConfig:
    # 与 `tests/conftest.py:ecommerce_config_small` 对齐，保证 CI 稳定且快速。
    return ECommerceConfig(
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


_CASES: Dict[str, CaseSpec] = {
    "smoke_basic": CaseSpec(
        case_id="smoke_basic",
        config=build_test_config_small(),
        targets=("order_id", "quantity", "unit_price"),
        row_limit=20,
    ),
    "smoke_derived": CaseSpec(
        case_id="smoke_derived",
        config=build_test_config_small(),
        targets=("order_id", "order_amount", "final_price"),
        row_limit=20,
    ),
}


def get_case(case_id: str) -> CaseSpec:
    if case_id not in _CASES:
        msg = "Unknown case_id={!r}. Known: {}".format(case_id, ", ".join(sorted(_CASES)))
        raise KeyError(msg)
    return _CASES[case_id]


def run_case(
    case_id: str,
    *,
    batch_size: int = 50,
    row_limit_override: Optional[int] = None,
    fields_to_check: Optional[Sequence[str]] = None,
) -> Tuple[List[Dict[str, Any]], VerificationResult]:
    """运行一个演示用例，并通过纯 Python 对照实现对拍验证输出正确性。

    返回 `(results, verification)`。
    """
    case = get_case(case_id)
    prev = get_config()
    set_config(case.config)
    try:
        demand = build_ecommerce_model()
        from scalim.execution.engine import ScalimEngine  # noqa: PLC0415
        from scalim.planning.builder import PlanBuilder  # noqa: PLC0415

        plan = PlanBuilder(demand).build(targets=list(case.targets))
        engine = ScalimEngine(demand=demand, plan=plan, batch_size=int(batch_size))

        row_limit = int(row_limit_override) if row_limit_override is not None else int(case.row_limit)
        main_rows = list(load_orders())[:row_limit]
        results = list(engine.run(main_rows=main_rows))

        check_fields = list(fields_to_check) if fields_to_check is not None else list(case.targets)
        verification = verify_scalim_output(results, fields_to_check=check_fields)
        return results, verification
    finally:
        set_config(prev)


__all__ = [
    "CaseSpec",
    "build_test_config_small",
    "get_case",
    "run_case",
]
