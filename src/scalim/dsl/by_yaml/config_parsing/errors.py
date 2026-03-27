from typing import Any, List, Optional

from ....exceptions import ScalimYamlError


class ScalimConfigValidationError(ScalimYamlError):
    errors: List[str]
    issues: List[Any]

    def __init__(self, message: str, errors: Optional[List[str]] = None, issues: Optional[List[Any]] = None) -> None:
        super(ScalimConfigValidationError, self).__init__(message)
        self.errors = errors or []
        self.issues = issues or []
