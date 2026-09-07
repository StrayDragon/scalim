"""`ConfigValidator` 的基于 `schema` 的未知字段检测.

加载 `JSON Schema` 并对配置中的未知字段进行校验报告.
"""

import json
import logging
from pathlib import Path
from typing import Any

from .unknown_fields import find_unknown_fields
from .validators.issues import (
    VALIDATION_SEVERITY_ERROR,
    VALIDATION_SEVERITY_WARNING,
    ValidationIssue,
)

__all__ = ()

_logger = logging.getLogger(__name__)


class ValidatorUnknownFieldsMixin:
    """提供 `schema` 加载与未知字段校验的 `Mixin`.

    组合类须在 `__init__` 中初始化 `_schema_path` 和 `_schema`.
    """

    _schema_path: str  # pyright: ignore[reportUninitializedInstanceVariable]
    _schema: dict[str, Any] | None  # pyright: ignore[reportUninitializedInstanceVariable]

    def _load_schema(self) -> dict[str, Any]:
        if self._schema is None:
            with Path(self._schema_path).open("r", encoding="utf-8") as f:
                self._schema = json.load(f)
        if self._schema is None:  # pragma: no cover  # pragma: allow-no-cover invariant: schema loaded or raised above
            msg = "Schema failed to load"
            raise RuntimeError(msg)
        return self._schema

    def _validate_unknown_fields(self, config: dict[str, Any], issues: list[ValidationIssue], *, strict: bool) -> None:
        try:
            schema = self._load_schema()
        except Exception as exc:  # noqa: BLE001
            if strict:
                issues.append(
                    ValidationIssue(
                        severity=VALIDATION_SEVERITY_ERROR,
                        message=f"加载 `JSON Schema` '{self._schema_path}' 失败; strict_unknown_fields=True 无法校验未知字段: {type(exc).__name__}",  # noqa: E501
                        path="schema",
                    )
                )
                return
            _logger.warning("加载 `JSON Schema` '%s' 失败; 未知字段校验已跳过", self._schema_path, exc_info=True)
            return

        severity = VALIDATION_SEVERITY_ERROR if strict else VALIDATION_SEVERITY_WARNING
        for unknown in find_unknown_fields(config, schema):
            issues.append(
                ValidationIssue(
                    severity=severity,
                    message=unknown.message,
                    path=unknown.path,
                    suggestions=unknown.suggestions,
                )
            )
