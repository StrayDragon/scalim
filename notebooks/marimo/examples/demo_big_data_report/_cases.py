"""`demo_big_data_report` 的场景用例注册表.

这个模块集中管理示例场景的配置与执行方式,确保:
- `tests/` 可以复用同一套场景定义,避免重复拼装配置/目标字段/对拍验证逻辑
- 示例始终有一个“用例真相来源”,避免不同入口各写一套

本模块刻意同时支持两种导入方式:
- 包导入: `notebooks.marimo.examples.demo_big_data_report._cases`
- 目录内脚本式导入: 通过 `sys.path` 注入后直接 `import _cases`
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
    # 与 `tests/conftest.py:ecommerce_config_small` 保持一致,确保 `CI` 稳定且足够快.
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
    """运行一个示例用例,并用纯 Python 对照组对输出做验证.

    Returns:
        (results, verification)
    """
    case = get_case(case_id)
    prev = get_config()
    set_config(case.config)
    try:
        demand = build_ecommerce_model()
        from scalim.execution import ScalimEngine  # noqa: PLC0415
        from scalim.planning import PlanBuilder  # noqa: PLC0415

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
