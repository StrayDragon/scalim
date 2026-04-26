import pytest

from scalim.ob.manager import ObserverManager


def test_observer_manager_mode_normalizes_and_rejects_invalid_values_cover_branches() -> None:
    manager = ObserverManager(mode=" CAPTURE ")
    assert manager.mode == "capture"

    state = ObserverManager().__getstate__()
    state.pop("mode", None)
    restored = ObserverManager.__new__(ObserverManager)
    restored.__setstate__(state)
    assert restored.mode == "process"

    with pytest.raises(TypeError, match="observer_manager.mode must be a str"):
        _ = ObserverManager(mode=1)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="observer_manager.mode must not be empty"):
        _ = ObserverManager(mode="   ")

    with pytest.raises(ValueError, match="Unknown observer_manager.mode"):
        _ = ObserverManager(mode="nope")
