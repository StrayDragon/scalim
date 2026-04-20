from scalim.execution.adaptive.errors import ScalimAdaptiveTaskTimeoutError


def test_adaptive_task_timeout_error_formats_items_branches() -> None:
    err = ScalimAdaptiveTaskTimeoutError(timeout_seconds=1.0, pending_task_keys=(), pending_field_keys=())
    text = str(err)
    assert "pending_field_keys=[]" in text
    assert "pending_task_keys=[]" in text

    many_field_keys = ["k{}".format(i) for i in range(12)]
    many_task_keys = [("k{}".format(i), i) for i in range(12)]

    err2 = ScalimAdaptiveTaskTimeoutError(timeout_seconds=1.0, pending_task_keys=many_task_keys, pending_field_keys=many_field_keys)
    assert "... (+2 more)" in str(err2)
