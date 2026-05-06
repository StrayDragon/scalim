import pytest

from scalim.ob._internal.common import ObserverManagerMode
from scalim.ob.manager import ObserverManager


def test_observer_manager_mode_normalizes_and_rejects_invalid_values_cover_branches() -> None:
    manager = ObserverManager(mode=ObserverManagerMode.CAPTURE)
    assert manager.mode == "capture"

    state = ObserverManager().__getstate__()
    state.pop("mode", None)
    restored = ObserverManager.__new__(ObserverManager)
    restored.__setstate__(state)
    assert restored.mode == "process"

    with pytest.raises(TypeError, match=r"observer_manager\.mode must be a ObserverManagerMode"):
        _ = ObserverManager(mode=1)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match=r"observer_manager\.mode must be a ObserverManagerMode"):
        _ = ObserverManager(mode="   ")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match=r"observer_manager\.mode must be a ObserverManagerMode"):
        _ = ObserverManager(mode="nope")  # type: ignore[arg-type]
