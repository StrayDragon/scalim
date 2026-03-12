import pytest


def mock_loader(*_args, **_kwargs):
    return {}


@pytest.fixture(scope="module")
def example_report_ir_module():
    from scalim_misc import example_report_ir

    example_report_ir.data_loader.random_delay = 0.0
    return example_report_ir


@pytest.fixture(scope="module")
def example_model(example_report_ir_module):
    return example_report_ir_module.build_order_report_model()


@pytest.fixture
def plan_builder(example_model):
    from scalim.planning import PlanBuilder

    return PlanBuilder(example_model)


@pytest.fixture
def engine_factory(example_model):
    from scalim.execution import ScalimEngine

    def _factory(plan, **kwargs):
        return ScalimEngine(demand=example_model, plan=plan, **kwargs)

    return _factory


@pytest.fixture(scope="module")
def ecommerce_config_small():
    from notebooks.marimo.demo_big_data_report._cases import build_test_config_small
    from notebooks.marimo.demo_big_data_report._shared import get_config, set_config

    prev = get_config()
    cfg = build_test_config_small()
    set_config(cfg)
    try:
        yield cfg
    finally:
        set_config(prev)


@pytest.fixture(scope="module")
def ecommerce_model_small(ecommerce_config_small):
    from notebooks.marimo.demo_big_data_report._shared import build_ecommerce_model

    return build_ecommerce_model(ecommerce_config_small)
