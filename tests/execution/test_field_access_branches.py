from scalim.execution.executor.helpers.field_access import contains_float


def test_contains_float_handles_empty_and_non_float_iterables() -> None:
    assert contains_float(()) is False
    assert contains_float((0, 1)) is False
    assert contains_float((0, 1.0)) is True

