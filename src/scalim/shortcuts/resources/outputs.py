"""从输出根目录(`output_root`)发现最新一次发布的 `outputs`(`books`/`files`) 的稳定门面.

目标:
- 用户不需要手写读取/解析 `<root>/manifest/latest.json`
- 用户不需要拼接 `versions/<id>` 等内部目录结构

运行时约束: `Python 3.6` 兼容.
"""

import json
from pathlib import Path
from typing import Dict, Mapping, Optional, Union, cast

from ..._internal.utils.json_like import JsonLike
from ...typedefs import RuntimeValue
from ...vendor.dataclassesx import dataclass

OutputRoot = Union[str, Path]


@dataclass(frozen=True)
class LatestOutputs:
    run_id: str
    books: Mapping[str, Path]
    files: Mapping[str, Path]


def _as_root(output_root: OutputRoot) -> Path:
    return Path(str(output_root)).expanduser()


def _is_safe_relpath(relpath: str) -> bool:
    p = Path(str(relpath))
    if p.is_absolute():
        return False
    return ".." not in p.parts


def _read_json_object(path: Path, *, what: str, output_root: Path) -> Mapping[str, JsonLike]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        msg = "{} not found: path={!r}, output_root={!r}".format(str(what), str(path), str(output_root))
        raise FileNotFoundError(msg) from exc
    except Exception as exc:
        msg = "Failed to parse {}: path={!r}, output_root={!r} ({}: {})".format(
            str(what),
            str(path),
            str(output_root),
            type(exc).__name__,
            exc,
        )
        raise ValueError(msg) from exc

    if not isinstance(payload, dict):
        msg = "{} must be a JSON object: path={!r}, output_root={!r}".format(str(what), str(path), str(output_root))
        raise TypeError(msg)
    return cast("Mapping[str, JsonLike]", payload)  # pragma: allow-cast json-load runtime boundary


def _require_non_empty_str(value: RuntimeValue, *, field: str, what: str, output_root: Path, path: Path) -> str:
    raw = str(value or "").strip()
    if not raw:
        msg = "{} missing required field {!r}: path={!r}, output_root={!r}".format(str(what), str(field), str(path), str(output_root))
        raise ValueError(msg)
    return str(raw)


def _parse_id_to_paths(
    value: RuntimeValue,
    *,
    kind: str,
    base_dir: Path,
    manifest_path: Path,
    output_root: Path,
) -> Dict[str, Path]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        msg = "Invalid version manifest: {!r} must be a JSON object: manifest={!r}, output_root={!r}".format(
            str(kind),
            str(manifest_path),
            str(output_root),
        )
        raise TypeError(msg)

    out: Dict[str, Path] = {}
    value_dict = cast("Mapping[object, object]", value)  # pragma: allow-cast json-load runtime boundary
    for raw_id, raw_relpath in value_dict.items():
        if not isinstance(raw_id, str):
            msg = "Invalid version manifest: {} id must be a string: manifest={!r}, output_root={!r}".format(
                str(kind), str(manifest_path), str(output_root)
            )
            raise TypeError(msg)
        rel = str(raw_relpath or "").strip()
        if not rel:
            continue
        if not _is_safe_relpath(rel):
            msg = "Invalid version manifest relpath: kind={!r}, id={!r}, relpath={!r}, manifest={!r}, output_root={!r}".format(
                str(kind),
                str(raw_id),
                rel,
                str(manifest_path),
                str(output_root),
            )
            raise ValueError(msg)
        out[str(raw_id)] = base_dir / rel
    return out


def load_latest_outputs(output_root: OutputRoot) -> LatestOutputs:
    """发现最新 `outputs` 快照(缺失时 `fail-fast`).

    返回:
    - `LatestOutputs`: `run_id` + `books`/`files` 映射(值为可直接使用的绝对路径/相对路径 `Path`).

    失败语义:
    - 缺失最新指示或解析失败时抛出异常(包含 `output_root` 与失败原因).
    """

    root = _as_root(output_root)
    latest_path = root / "manifest" / "latest.json"
    if not latest_path.is_file():
        msg = "Latest outputs pointer not found: path={!r}, output_root={!r}".format(str(latest_path), str(root))
        raise FileNotFoundError(msg)

    latest = _read_json_object(latest_path, what="latest outputs pointer", output_root=root)
    run_id = _require_non_empty_str(
        latest.get("version_id"), field="version_id", what="latest outputs pointer", output_root=root, path=latest_path
    )
    relpath = _require_non_empty_str(
        latest.get("version_manifest_relpath"),
        field="version_manifest_relpath",
        what="latest outputs pointer",
        output_root=root,
        path=latest_path,
    )
    if not _is_safe_relpath(relpath):
        msg = "Invalid latest outputs pointer: version_manifest_relpath must be a safe relative path: {!r} (output_root={!r})".format(
            relpath, str(root)
        )
        raise ValueError(msg)

    manifest_path = root / relpath
    manifest = _read_json_object(manifest_path, what="version manifest", output_root=root)

    base_dir = manifest_path.parent
    books = _parse_id_to_paths(
        manifest.get("books"),
        kind="books",
        base_dir=base_dir,
        manifest_path=manifest_path,
        output_root=root,
    )
    files = _parse_id_to_paths(
        manifest.get("files"),
        kind="files",
        base_dir=base_dir,
        manifest_path=manifest_path,
        output_root=root,
    )

    # 诊断: 提前验证 `manifest` 指示的产物路径存在(避免返回不可用路径让调用方二次排障).
    missing = [("book", bid, p) for bid, p in books.items() if not p.exists()] + [
        ("file", fid, p) for fid, p in files.items() if not p.exists()
    ]
    if missing:
        kinds = ", ".join(["{}:{}={!r}".format(k, i, str(p)) for k, i, p in missing[:5]])
        msg = "Latest outputs manifest points to missing artifacts: output_root={!r}, run_id={!r}, missing={}".format(
            str(root), run_id, kinds
        )
        raise FileNotFoundError(msg)

    return LatestOutputs(run_id=str(run_id), books=dict(books), files=dict(files))


def try_load_latest_outputs(output_root: OutputRoot) -> Optional[LatestOutputs]:
    """尝试发现最新 `outputs` 快照(缺失返回 `None`).

    缺失 `latest` 指示时返回 `None`;其它解析/一致性错误仍抛出异常.
    """

    root = _as_root(output_root)
    latest_path = root / "manifest" / "latest.json"
    if not latest_path.is_file():
        return None
    return load_latest_outputs(root)


def latest_book_path(output_root: OutputRoot, *, book_id: str) -> Path:
    latest = load_latest_outputs(output_root)
    bid = str(book_id or "").strip()
    if not bid:
        msg = "book_id must be a non-empty string"
        raise ValueError(msg)
    try:
        return latest.books[bid]
    except KeyError as exc:
        msg = "Latest outputs missing book_id: {!r} (output_root={!r}, run_id={!r})".format(bid, str(_as_root(output_root)), latest.run_id)
        raise KeyError(msg) from exc


def latest_file_path(output_root: OutputRoot, *, file_id: str) -> Path:
    latest = load_latest_outputs(output_root)
    fid = str(file_id or "").strip()
    if not fid:
        msg = "file_id must be a non-empty string"
        raise ValueError(msg)
    try:
        return latest.files[fid]
    except KeyError as exc:
        msg = "Latest outputs missing file_id: {!r} (output_root={!r}, run_id={!r})".format(fid, str(_as_root(output_root)), latest.run_id)
        raise KeyError(msg) from exc


__all__ = (
    "LatestOutputs",
    "latest_book_path",
    "latest_file_path",
    "load_latest_outputs",
    "try_load_latest_outputs",
)
