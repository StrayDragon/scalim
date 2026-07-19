"""版本化输出 (`D-2`) 辅助函数.

本模块实现 `output root` 目录 + `versions/<version_id>` 布局, 并负责 `manifest` 指示文件的原子更新.

运行时约束:
- 必须保持 `Python 3.6` 兼容.
"""

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, cast

from .._internal.utils.json_like import JsonLike
from ..sinks._internal.base import atomic_replace_temp_path, best_effort_remove_temp_path, create_temp_path
from ..typedefs import RuntimeValue
from ..vendor.dataclassesx import dataclass

_SAFE_VERSION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


@dataclass(frozen=True)
class OutputRootLayout:
    root: Path
    versions_dir: Path
    manifest_dir: Path


@dataclass(frozen=True)
class ParsedVersionedOutputPath:
    """解析后的版本化输出路径 (位于 `<root>/versions/<version_id>/...`)."""

    root: Path
    version_id: str
    kind: str
    artifact_id: str
    artifact_relpath: str


def validate_version_id(version_id: str) -> str:
    vid = str(version_id or "").strip()
    if not vid or _SAFE_VERSION_ID_RE.match(vid) is None:
        msg = "version_id must be a safe path segment: {!r}".format(vid)
        raise ValueError(msg)
    return str(vid)


def _validate_output_id(value: str, *, kind: str) -> str:
    raw = str(value or "").strip()
    if not raw or _SAFE_VERSION_ID_RE.match(raw) is None:
        msg = "{} must be a safe path segment: {!r}".format(str(kind), raw)
        raise ValueError(msg)
    return str(raw)


def ensure_output_root_layout(root: Path) -> OutputRootLayout:
    root_obj = Path(str(root))
    root_obj.mkdir(parents=True, exist_ok=True)
    versions_dir = root_obj / "versions"
    manifest_dir = root_obj / "manifest"
    versions_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)
    return OutputRootLayout(root=root_obj, versions_dir=versions_dir, manifest_dir=manifest_dir)


def ensure_version_dir(layout: OutputRootLayout, *, version_id: str) -> Path:
    """创建 `<root>/versions/<version_id>/`; 若目录已存在则立即报错."""
    vid = validate_version_id(version_id)
    version_dir = layout.versions_dir / str(vid)
    try:
        version_dir.mkdir(parents=False, exist_ok=False)
    except FileExistsError as exc:
        msg = "Version directory already exists (possible concurrent writers or reused version_id): {!r}".format(str(version_dir))
        raise FileExistsError(msg) from exc
    return version_dir


def version_dir(layout: OutputRootLayout, *, version_id: str) -> Path:
    vid = validate_version_id(version_id)
    return layout.versions_dir / str(vid)


def latest_path(layout: OutputRootLayout) -> Path:
    return layout.manifest_dir / "latest.json"


def version_manifest_path(layout: OutputRootLayout, *, version_id: str) -> Path:
    return version_dir(layout, version_id=str(version_id)) / "manifest.json"


def version_manifest_relpath(*, version_id: str) -> str:
    vid = validate_version_id(version_id)
    return "{}/{}".format("versions", "{}/manifest.json".format(str(vid)))


def file_output_relpath(*, file_id: str) -> str:
    fid = _validate_output_id(str(file_id), kind="file_id")
    return "files/{}.csv".format(fid)


def book_output_relpath(*, book_id: str) -> str:
    bid = _validate_output_id(str(book_id), kind="book_id")
    return "books/{}.xlsx".format(bid)


def file_output_path(layout: OutputRootLayout, *, version_id: str, file_id: str) -> Path:
    rel = file_output_relpath(file_id=str(file_id))
    return version_dir(layout, version_id=str(version_id)) / rel


def book_output_path(layout: OutputRootLayout, *, version_id: str, book_id: str) -> Path:
    rel = book_output_relpath(book_id=str(book_id))
    return version_dir(layout, version_id=str(version_id)) / rel


def _atomic_write_json(path: Path, payload: RuntimeValue) -> None:
    out_path = str(path)
    path_obj = Path(out_path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    temp_path = create_temp_path(out_path, ".json.tmp")
    try:
        _ = Path(temp_path).write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        atomic_replace_temp_path(temp_path, out_path)
    except Exception:
        best_effort_remove_temp_path(temp_path)
        raise


def write_version_manifest(
    layout: OutputRootLayout,
    *,
    version_id: str,
    created_at_unix_s: Optional[int] = None,
    books: Optional[Mapping[str, str]] = None,
    files: Optional[Mapping[str, str]] = None,
) -> Path:
    """写入 `<root>/versions/<version_id>/manifest.json` (原子替换)."""
    vid = validate_version_id(version_id)
    manifest_path = version_manifest_path(layout, version_id=str(vid))
    payload: Dict[str, Any] = {
        "version_id": str(vid),
        "created_at_unix_s": int(time.time()) if created_at_unix_s is None else int(created_at_unix_s),
        "books": dict(books or {}),
        "files": dict(files or {}),
    }
    _atomic_write_json(manifest_path, payload)
    return manifest_path


def update_latest(
    layout: OutputRootLayout,
    *,
    version_id: str,
    version_manifest_relpath: str,
) -> Path:
    """原子更新 `<root>/manifest/latest.json` (并发语义为 `last-writer-wins`)."""
    vid = validate_version_id(version_id)
    rel = str(version_manifest_relpath or "").strip()
    if not rel:
        msg = "version_manifest_relpath must be a non-empty string"
        raise ValueError(msg)
    out_path = latest_path(layout)
    payload = {
        "version_id": str(vid),
        "version_manifest_relpath": str(rel),
    }
    _atomic_write_json(out_path, payload)
    return out_path


def parse_versioned_output_path(path: Path) -> ParsedVersionedOutputPath:
    p = Path(str(path))
    parts = p.parts

    versions_idx: Optional[int] = None
    for i in range(len(parts) - 1, -1, -1):
        if parts[i] == "versions":
            versions_idx = i
            break

    if versions_idx is None:
        msg = "Not a versioned output path (missing 'versions' segment): {!r}".format(str(p))
        raise ValueError(msg)

    # 形状要求: `<root>/versions/<version_id>/<kind>/<filename>`
    if len(parts) < versions_idx + 4:
        msg = "Invalid versioned output path shape: {!r}".format(str(p))
        raise ValueError(msg)

    root_parts = parts[:versions_idx]
    root = Path(*root_parts) if root_parts else Path()

    version_id = validate_version_id(parts[versions_idx + 1])
    kind = str(parts[versions_idx + 2])
    filename = str(parts[versions_idx + 3])

    if kind == "books":
        if not filename.endswith(".xlsx"):
            msg = "Invalid versioned book output filename: {!r}".format(filename)
            raise ValueError(msg)
        artifact_id = filename[: -len(".xlsx")]
        rel = book_output_relpath(book_id=artifact_id)
        return ParsedVersionedOutputPath(
            root=root,
            version_id=version_id,
            kind=kind,
            artifact_id=artifact_id,
            artifact_relpath=rel,
        )

    if kind == "files":
        if not filename.endswith(".csv"):
            msg = "Invalid versioned file output filename: {!r}".format(filename)
            raise ValueError(msg)
        artifact_id = filename[: -len(".csv")]
        rel = file_output_relpath(file_id=artifact_id)
        return ParsedVersionedOutputPath(
            root=root,
            version_id=version_id,
            kind=kind,
            artifact_id=artifact_id,
            artifact_relpath=rel,
        )

    msg = "Unknown versioned output kind: {!r} (path={!r})".format(kind, str(p))
    raise ValueError(msg)


def read_latest(root: Path) -> Dict[str, JsonLike]:
    p = Path(str(root)) / "manifest" / "latest.json"
    return cast("Dict[str, JsonLike]", json.loads(p.read_text("utf-8")))  # pragma: allow-cast json load runtime boundary


def read_version_manifest(root: Path, *, version_id: str) -> Dict[str, JsonLike]:
    p = Path(str(root)) / "versions" / str(validate_version_id(version_id)) / "manifest.json"
    return cast("Dict[str, JsonLike]", json.loads(p.read_text("utf-8")))  # pragma: allow-cast json load runtime boundary


__all__ = (
    "OutputRootLayout",
    "ParsedVersionedOutputPath",
    "book_output_path",
    "book_output_relpath",
    "ensure_output_root_layout",
    "ensure_version_dir",
    "file_output_path",
    "file_output_relpath",
    "latest_path",
    "parse_versioned_output_path",
    "read_latest",
    "read_version_manifest",
    "update_latest",
    "validate_version_id",
    "version_dir",
    "version_manifest_path",
    "version_manifest_relpath",
    "write_version_manifest",
)
