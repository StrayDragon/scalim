import pytest


@pytest.fixture(scope="module")
def example_report_ir_module():
    from scalim_misc import example_report_ir

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(example_report_ir, "data_loader", example_report_ir.PandasDataLoader(random_delay=0.0))
    try:
        yield example_report_ir
    finally:
        monkeypatch.undo()


@pytest.fixture(scope="module")
def example_model(example_report_ir_module):
    return example_report_ir_module.build_order_report_model()


@pytest.fixture(scope="module")
def example_runtime_bindings(example_report_ir_module):
    return example_report_ir_module.build_order_report_runtime_bindings()


@pytest.fixture
def plan_builder(example_model):
    from scalim.planning import PlanBuilder

    return PlanBuilder(example_model)


@pytest.fixture
def engine_factory(example_model, example_runtime_bindings):
    from scalim.execution.engine import ScalimEngine

    def _factory(plan, **kwargs):
        return ScalimEngine(demand=example_model, plan=plan, runtime_bindings=example_runtime_bindings, **kwargs)

    return _factory


@pytest.fixture(scope="module")
def ecommerce_config_small():
    from scalim_misc.demo_big_data_report.cases import build_test_config_small
    from tests.support.demo_big_data_report_config import patched_ecommerce_config

    cfg = build_test_config_small()
    with patched_ecommerce_config(cfg):
        yield cfg


@pytest.fixture(scope="module")
def ecommerce_model_small(ecommerce_config_small):
    from scalim_misc.demo_big_data_report.shared import build_ecommerce_model

    return build_ecommerce_model(ecommerce_config_small)
