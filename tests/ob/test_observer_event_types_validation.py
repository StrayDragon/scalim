import pytest

from scalim.ob._internal.common import validate_event_types


def test_validate_event_types_rejects_unknown_event_type() -> None:
    class _Observer:
        pass

    observer = _Observer()
    with pytest.raises(ValueError, match=r"unknown event type"):
        validate_event_types(observer, {"unknown-event-type"})
