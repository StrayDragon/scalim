from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Any, List, Optional, Tuple

VALIDATION_SEVERITY_ERROR = "error"
VALIDATION_SEVERITY_WARNING = "warning"

MAX_VALIDATION_ERROR_LINES = 50


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    message: str
    path: str = ""
    code: Optional[str] = None
    suggestions: Tuple[str, ...] = ()


@dataclass
class ValidationReport:
    issues: List[ValidationIssue] = dataclass_field(default_factory=list)

    def add(self, issue: ValidationIssue) -> None:
        self.issues.append(issue)

    def add_error(self, message: str, path: str = "", code: Optional[str] = None) -> None:
        self.add(ValidationIssue(severity=VALIDATION_SEVERITY_ERROR, message=message, path=path, code=code))

    def add_warning(self, message: str, path: str = "", code: Optional[str] = None) -> None:
        self.add(ValidationIssue(severity=VALIDATION_SEVERITY_WARNING, message=message, path=path, code=code))

    @classmethod
    def from_errors(cls, errors: List[Any]) -> "ValidationReport":
        report = cls()
        for item in errors:
            if isinstance(item, ValidationIssue):
                report.add(item)
            else:
                report.add_error(str(item))
        return report

    def errors(self) -> List[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == VALIDATION_SEVERITY_ERROR]

    def warnings(self) -> List[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == VALIDATION_SEVERITY_WARNING]

    def ok(self) -> bool:
        return not self.errors()
