import pytest

from scalim_misc.demo_big_data_report.cases import run_case


pytestmark = pytest.mark.slow


@pytest.mark.parametrize("case_id", ["smoke_basic", "smoke_derived"])
def test_big_data_demo_verification_small(case_id: str) -> None:
    _results, verification = run_case(case_id, batch_size=10, row_limit_override=20)
    assert verification.passed, verification.summary
