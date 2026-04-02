import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from ....workflow.errors import ScalimWorkflowConfigError
from .._internal.config_parsing.error_envelope import ScalimYamlValidationError
from .._internal.config_parsing.template_precompile import DEFAULT_RENDERED_YAML_MAX_LEN, maybe_precompile_yaml_text
from .._internal.config_parsing.yaml_load import load_yaml_mapping_text
from .._public_template_sandbox import validate_public_template_sandbox
from ._models import WorkflowConfig
from ._parse import load_workflow_config_from_mapping


def load_workflow_config(
    workflow_yaml_path: str,
    *,
    template_vars: Optional[Mapping[str, object]] = None,
    template_sandbox: str = "safe",
    rendered_yaml_max_len: int = DEFAULT_RENDERED_YAML_MAX_LEN,
) -> WorkflowConfig:
    template_sandbox = validate_public_template_sandbox(template_sandbox)
    msg: str
    yaml_path = Path(str(workflow_yaml_path or "")).expanduser()
    try:
        text = yaml_path.read_text(encoding="utf-8")
    except Exception as exc:
        msg = "Failed to read workflow YAML: {}: {}".format(type(exc).__name__, exc)
        raise ScalimWorkflowConfigError(msg, path="(file)") from exc

    try:
        text = maybe_precompile_yaml_text(
            text,
            template_vars=template_vars,
            context_label="工作流 `YAML` 文件 `{}`".format(str(yaml_path)),
            context_kind="workflow",
            template_sandbox=template_sandbox,
            rendered_yaml_max_len=rendered_yaml_max_len,
        )
    except ValueError as exc:
        raise ScalimWorkflowConfigError(str(exc), path="(file)") from exc

    try:
        loaded, _locations, _lines = load_yaml_mapping_text(
            text,
            source_path=str(yaml_path),
            detect_duplicate_keys=True,
        )
    except ScalimYamlValidationError as exc:
        first = exc.errors[0] if exc.errors else None
        msg = first.message if first is not None else str(exc)
        raise ScalimWorkflowConfigError(msg, path=str(first.path if first is not None else "(root)")) from None

    return load_workflow_config_from_mapping(loaded)


def validate_workflow_yaml_text_json(
    yaml_text: str,
    strict_unknown_fields: bool = False,  # noqa: FBT001, FBT002
    schema_path: Optional[str] = None,
) -> str:
    """返回与 YAML DSL 编辑器的“精确校验器”兼容的 JSON 载荷(`Workflow` 版).

    注意:
    - `workflow` YAML 与 `demand` YAML 是两套语义;此校验器只做 `workflow` 语义校验.
    - 目前不基于 `schema_path` 做 `JSONSchema` 校验(结构校验建议交给 `YAML LSP`).
    """
    _ = (strict_unknown_fields, schema_path)
    payload = _validate_workflow_yaml_text(yaml_text)
    return json.dumps(payload, ensure_ascii=False)


def _validate_workflow_yaml_text(yaml_text: str) -> Dict[str, Any]:
    try:
        yaml_data, _locations, _lines = load_yaml_mapping_text(
            yaml_text,
            source_path="(memory)",
            detect_duplicate_keys=True,
        )
    except ScalimYamlValidationError as exc:
        first = exc.errors[0] if exc.errors else None
        message = first.message if first is not None else str(exc)
        return {"ok": False, "errors": [{"path": "(root)", "message": message}], "warnings": []}

    try:
        _ = load_workflow_config_from_mapping(yaml_data)
    except ScalimWorkflowConfigError as exc:
        return {
            "ok": False,
            "errors": [{"path": str(exc.path or "(root)"), "message": str(exc)}],
            "warnings": [],
        }

    return {"ok": True, "errors": [], "warnings": []}


__all__ = ()
