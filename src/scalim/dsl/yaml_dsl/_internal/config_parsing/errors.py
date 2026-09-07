from typing import Any

from .....exceptions import ScalimYamlError


class ScalimConfigValidationError(ScalimYamlError):
    errors: list[str]
    issues: list[Any]

    def __init__(self, message: str, errors: list[str] | None = None, issues: list[Any] | None = None) -> None:
        super().__init__(message)
        self.errors = errors or []
        self.issues = issues or []


__all__ = ()
