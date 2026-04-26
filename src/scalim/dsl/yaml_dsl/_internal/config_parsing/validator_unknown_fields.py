"""`ConfigValidator` 的基于 `schema` 的未知字段检测.

加载 `JSON Schema` 并对配置中的未知字段进行校验报告.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

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
    _schema: Optional[Dict[str, Any]]  # pyright: ignore[reportUninitializedInstanceVariable]

    def _load_schema(self) -> Dict[str, Any]:
        if self._schema is None:
            with Path(self._schema_path).open("r", encoding="utf-8") as f:
                self._schema = json.load(f)
        if self._schema is None:  # pragma: no cover  # pragma: allow-no-cover invariant: schema loaded or raised above
            msg = "Schema failed to load"
            raise RuntimeError(msg)
        return self._schema

    def _validate_unknown_fields(self, config: Dict[str, Any], issues: List[ValidationIssue], *, strict: bool) -> None:
        try:
            schema = self._load_schema()
        except Exception as exc:  # noqa: BLE001
            if strict:
                issues.append(
                    ValidationIssue(
                        severity=VALIDATION_SEVERITY_ERROR,
                        message="加载 `JSON Schema` '{}' 失败; strict_unknown_fields=True 无法校验未知字段: {}".format(
                            self._schema_path,
                            type(exc).__name__,
                        ),
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
