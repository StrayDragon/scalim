from typing import Any, Dict


def mock_loader(*_args: Any, **_kwargs: Any) -> Dict[str, Any]:
    return {}


__all__ = [
    "mock_loader",
]
