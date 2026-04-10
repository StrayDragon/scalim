import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union
from urllib.parse import unquote, urlparse

from tests.support.pathing import repo_root

JsonValue = Union[None, bool, int, float, str, List["JsonValue"], Dict[str, "JsonValue"]]


def _normalize_uri_prefix(uri: str, *, placeholder: str, root_uri: str) -> str:
    if uri == root_uri:
        return "file://{placeholder}".format(placeholder=placeholder)
    prefix = root_uri.rstrip("/") + "/"
    if uri.startswith(prefix):
        return "file://{placeholder}/{rest}".format(placeholder=placeholder, rest=uri[len(prefix) :])
    return uri


def _normalize_path_prefix(path: str, *, placeholder: str, root_path: str) -> str:
    if path == root_path:
        return str(placeholder)
    prefix = root_path.rstrip("/") + "/"
    if path.startswith(prefix):
        return str(placeholder) + "/" + path[len(prefix) :]
    return path


def normalize_env_paths(value: str, *, workspace: Path) -> str:
    # Keep snapshots stable across machines:
    # - tmp workspace paths -> `<WORKSPACE>`
    # - repo root paths -> `<REPO_ROOT>`
    ws_path = str(workspace.resolve())
    ws_uri = workspace.resolve().as_uri()

    repo = repo_root().resolve()
    repo_path = str(repo)
    repo_uri = repo.as_uri()

    out = str(value)
    # Prefer global replacements first (paths may appear in the middle of hover strings, diagnostics, etc.).
    out = out.replace(ws_uri.rstrip("/") + "/", "file://<WORKSPACE>/")
    out = out.replace(ws_uri, "file://<WORKSPACE>")
    out = out.replace(repo_uri.rstrip("/") + "/", "file://<REPO_ROOT>/")
    out = out.replace(repo_uri, "file://<REPO_ROOT>")
    out = out.replace(ws_path.rstrip("/") + "/", "<WORKSPACE>/")
    out = out.replace(ws_path, "<WORKSPACE>")
    out = out.replace(repo_path.rstrip("/") + "/", "<REPO_ROOT>/")
    out = out.replace(repo_path, "<REPO_ROOT>")

    # Keep the more conservative prefix rules as a backstop.
    out = _normalize_uri_prefix(out, placeholder="<WORKSPACE>", root_uri=ws_uri)
    out = _normalize_uri_prefix(out, placeholder="<REPO_ROOT>", root_uri=repo_uri)
    out = _normalize_path_prefix(out, placeholder="<WORKSPACE>", root_path=ws_path)
    out = _normalize_path_prefix(out, placeholder="<REPO_ROOT>", root_path=repo_path)
    return out


def normalize_json(value: Any, *, workspace: Path) -> Any:
    if isinstance(value, str):
        return normalize_env_paths(value, workspace=workspace)
    if isinstance(value, list):
        return [normalize_json(item, workspace=workspace) for item in value]
    if isinstance(value, dict):
        return {str(k): normalize_json(v, workspace=workspace) for k, v in value.items()}
    return value


def _range_start_key(rng: Any) -> Tuple[int, int]:
    if not isinstance(rng, dict):
        return (0, 0)
    start = rng.get("start") or {}
    return (int(start.get("line", 0)), int(start.get("character", 0)))


def normalize_diagnostics(diagnostics: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for diag in diagnostics:
        out.append(
            {
                "range": diag.get("range") or {},
                "severity": diag.get("severity"),
                "code": diag.get("code"),
                "source": diag.get("source"),
                "message": diag.get("message"),
            }
        )

    def _key(item: Dict[str, Any]) -> Tuple[Tuple[int, int], int, str]:
        rng = item.get("range") or {}
        sev = int(item.get("severity") or 0)
        msg = str(item.get("message") or "")
        return (_range_start_key(rng), sev, msg)

    out.sort(key=_key)
    return out


def normalize_locations(locations: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for loc in locations:
        out.append(
            {
                "uri": loc.get("uri"),
                "range": loc.get("range") or {},
            }
        )

    def _key(item: Dict[str, Any]) -> Tuple[str, Tuple[int, int]]:
        uri = str(item.get("uri") or "")
        rng = item.get("range") or {}
        return (uri, _range_start_key(rng))

    out.sort(key=_key)
    return out


def normalize_hover(hover: Any) -> Dict[str, Any]:
    if not isinstance(hover, dict):
        return {"contents": str(hover)}

    contents = hover.get("contents")
    if isinstance(contents, dict):
        return {"contents": str(contents.get("value") or "")}
    if isinstance(contents, list):
        return {"contents": "\n".join(str(c) for c in contents)}
    return {"contents": str(contents or "")}


def normalize_completion_items(result: Any) -> List[Dict[str, Any]]:
    items: Any = []
    if isinstance(result, dict):
        items = result.get("items") or []
    elif isinstance(result, list):
        items = result

    out: List[Dict[str, Any]] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "label": item.get("label"),
                "kind": item.get("kind"),
                "detail": item.get("detail"),
                "sortText": item.get("sortText"),
            }
        )

    def _key(entry: Dict[str, Any]) -> Tuple[str, str]:
        sort_text = str(entry.get("sortText") or "")
        label = str(entry.get("label") or "")
        return (sort_text, label)

    out.sort(key=_key)
    return out


def normalize_code_actions(actions: Any) -> List[Dict[str, Any]]:
    if not isinstance(actions, list):
        return []

    out: List[Dict[str, Any]] = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        cmd = action.get("command") or {}
        out.append(
            {
                "title": action.get("title"),
                "kind": action.get("kind"),
                "command": {
                    "command": cmd.get("command"),
                    "arguments": cmd.get("arguments") or [],
                }
                if isinstance(cmd, dict)
                else cmd,
                "edit": action.get("edit"),
            }
        )

    def _key(entry: Dict[str, Any]) -> Tuple[str, str]:
        cmd = entry.get("command") or {}
        cmd_name = cmd.get("command") if isinstance(cmd, dict) else ""
        return (str(cmd_name or ""), str(entry.get("title") or ""))

    out.sort(key=_key)
    return out


def assert_no_path_leaks(payload: Any, *, workspace: Path) -> None:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    ws_path = str(workspace.resolve())
    repo_path = str(repo_root().resolve())
    if ws_path and ws_path in raw:
        raise AssertionError("snapshot leaked workspace path: {}".format(ws_path))
    if repo_path and repo_path in raw:
        raise AssertionError("snapshot leaked repo root path: {}".format(repo_path))


def uri_to_path(uri: str) -> Optional[Path]:
    parsed = urlparse(str(uri or ""))
    if parsed.scheme != "file":
        return None
    raw_path = unquote(parsed.path or "")
    if not raw_path:
        return None
    return Path(raw_path).expanduser().resolve(strict=False)


__all__ = [
    "assert_no_path_leaks",
    "normalize_code_actions",
    "normalize_completion_items",
    "normalize_diagnostics",
    "normalize_env_paths",
    "normalize_hover",
    "normalize_json",
    "normalize_locations",
    "uri_to_path",
]
