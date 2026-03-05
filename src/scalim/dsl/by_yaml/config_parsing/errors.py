from typing import Any, List, Optional


class ConfigValidationError(Exception):
    errors: List[str]
    issues: List[Any]

    def __init__(self, message: str, errors: Optional[List[str]] = None, issues: Optional[List[Any]] = None) -> None:
        super(ConfigValidationError, self).__init__(message)
        self.errors = errors or []
        self.issues = issues or []
