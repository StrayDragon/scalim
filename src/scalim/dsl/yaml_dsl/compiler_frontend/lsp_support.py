"""供 `scalim-yaml-dsl-lsp` 调用的适配层(运行时 `Python 3.6` 兼容).

目标:
- 让 `LSP` 包不再直接依赖 `scalim.dsl.yaml_dsl._internal.*` 的模块路径;
- 在不改变既有行为的前提下,把内部实现的演进成本收敛在主框架(`src/scalim`)内.

说明:
- 这里以“重新导出”为主,避免在 `LSP` 包内复制一套解析/校验逻辑.
- 该模块并不承诺长期稳定的 `API`;但它提供了一个可控的边界,便于后续逐步替换为更高层的编译前端产物.
"""

from .._internal.config_parsing.allowed_paths import normalize_allowed_yaml_roots, validate_resolved_yaml_path_within_roots
from .._internal.config_parsing.error_envelope import ErrorEnvelope, ErrorLoc, ScalimYamlValidationError
from .._internal.config_parsing.jsonschema_issues import ScalimJsonSchemaCollectorError, collect_jsonschema_validation_issues
from .._internal.config_parsing.models import FieldDef, FieldDefIndex, RawDemand, collect_field_defs
from .._internal.config_parsing.parsers.outputs import ParserOutputsMixin
from .._internal.config_parsing.presets import load_scalim_preset_yaml_text
from .._internal.config_parsing.project_config import YamlDslProjectConfig, load_yaml_dsl_project_config
from .._internal.config_parsing.security import SecureComputeEngine
from .._internal.config_parsing.unknown_fields import find_unknown_fields
from .._internal.config_parsing.validator import ConfigValidator
from .._internal.config_parsing.validators.issues import VALIDATION_SEVERITY_ERROR, ValidationIssue
from .._internal.config_parsing.yaml_load import envelope_from_validation_issue, error_loc_for_yaml_path, load_yaml_mapping_text

__all__ = (
    "VALIDATION_SEVERITY_ERROR",
    "ConfigValidator",
    "ErrorEnvelope",
    "ErrorLoc",
    "FieldDef",
    "FieldDefIndex",
    "ParserOutputsMixin",
    "RawDemand",
    "ScalimJsonSchemaCollectorError",
    "ScalimYamlValidationError",
    "SecureComputeEngine",
    "ValidationIssue",
    "YamlDslProjectConfig",
    "collect_field_defs",
    "collect_jsonschema_validation_issues",
    "envelope_from_validation_issue",
    "error_loc_for_yaml_path",
    "find_unknown_fields",
    "load_scalim_preset_yaml_text",
    "load_yaml_dsl_project_config",
    "load_yaml_mapping_text",
    "normalize_allowed_yaml_roots",
    "validate_resolved_yaml_path_within_roots",
)
