from scalim.ob._internal.manager_state import ObserverManagerStateMixin


class _DummyState(ObserverManagerStateMixin):
    def _rebuild_subscription_cache(self) -> None:
        return None


def test_observer_manager_state_sample_result_falls_back_to_summary_for_object() -> None:
    manager = _DummyState()

    result = manager.sample_result(object())
    assert result == {"type": "object"}
