import re
from collections.abc import Mapping, Sequence
from pathlib import Path

from ....workflow.errors import ScalimWorkflowConfigError
from .._internal.config_parsing.allowed_paths import normalize_allowed_yaml_roots, validate_resolved_yaml_path_within_roots

_ALIAS_DEMAND_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):/(.+)$")


def resolve_workflow_demand_path(
    demand: str,
    *,
    workflow_yaml_path: str,
    path_aliases: Mapping[str, str] | None = None,
    run_id: str | None = None,
    allowed_yaml_roots: Sequence[str | Path] | None = None,
) -> Path:
    msg: str
    raw = str(demand or "").strip()
    if not raw:
        msg = "run.demand must be a non-empty string"
        raise ScalimWorkflowConfigError(msg, path="workflow.runs[*].demand")

    wf_path = Path(str(workflow_yaml_path or "")).expanduser().resolve(strict=False)
    base_dir = wf_path.parent

    roots: Sequence[Path]
    try:
        roots = normalize_allowed_yaml_roots(allowed_yaml_roots, default_root=base_dir)
    except ValueError as exc:
        msg = f"Invalid allowed_yaml_roots: {exc}"
        if run_id:
            msg = f"{msg} (run_id={run_id})"
        raise ScalimWorkflowConfigError(msg, path="workflow.runs[*].demand") from exc

    if raw.startswith("@/"):
        alias = "@"
        rel = raw[2:]
        return _resolve_alias_path(
            alias=alias,
            rel=rel,
            raw=raw,
            path_aliases=path_aliases,
            run_id=run_id,
            allowed_yaml_roots=roots,
        )

    m = _ALIAS_DEMAND_RE.match(raw)
    if m is not None:
        alias = m.group(1)
        rel = m.group(2)
        return _resolve_alias_path(
            alias=alias,
            rel=rel,
            raw=raw,
            path_aliases=path_aliases,
            run_id=run_id,
            allowed_yaml_roots=roots,
        )

    p = Path(raw).expanduser()
    resolved = p.resolve(strict=False) if p.is_absolute() else (base_dir / p).resolve(strict=False)
    try:
        validate_resolved_yaml_path_within_roots(
            raw_path=raw,
            base_dir=base_dir,
            resolved_path=resolved,
            allowed_yaml_roots=roots,
            context_label="workflow.runs[*].demand",
        )
    except ValueError as exc:
        msg = str(exc)
        if run_id:
            msg = f"{msg} (run_id={run_id})"
        raise ScalimWorkflowConfigError(msg, path="workflow.runs[*].demand") from exc
    return resolved


def _resolve_alias_path(
    *,
    alias: str,
    rel: str,
    raw: str,
    path_aliases: Mapping[str, str] | None,
    run_id: str | None,
    allowed_yaml_roots: Sequence[Path],
) -> Path:
    msg: str
    aliases = path_aliases or {}
    base_raw = aliases.get(alias)
    if base_raw is None:
        msg = f"Unknown path alias '{alias}' for demand path '{raw}'"
        if run_id:
            msg = f"{msg} (run_id={run_id})"
        raise ScalimWorkflowConfigError(msg, path="workflow.runs[*].demand")
    base = Path(str(base_raw)).expanduser()
    rel_str = str(rel or "").lstrip("/")
    if not rel_str:
        msg = f"Invalid demand alias path '{raw}'"
        if run_id:
            msg = f"{msg} (run_id={run_id})"
        raise ScalimWorkflowConfigError(msg, path="workflow.runs[*].demand")
    rel_path = Path(rel_str)
    resolved = (base / rel_path).resolve(strict=False)
    try:
        validate_resolved_yaml_path_within_roots(
            raw_path=raw,
            base_dir=base,
            resolved_path=resolved,
            allowed_yaml_roots=allowed_yaml_roots,
            context_label=f"workflow.runs[*].demand(alias={alias}, alias_base={base!s})",
        )
    except ValueError as exc:
        msg = str(exc)
        if run_id:
            msg = f"{msg} (run_id={run_id})"
        raise ScalimWorkflowConfigError(msg, path="workflow.runs[*].demand") from exc
    return resolved


__all__ = ()
