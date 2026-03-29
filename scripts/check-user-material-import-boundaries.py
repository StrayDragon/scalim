#!/usr/bin/env python3
"""检查用户材料导入边界(禁止内部/未编目导入).

扫描范围(用户可见材料):
- `docs/doc/**`
- `notebooks/marimo/**`
- `artifacts/skills/**`

约束(SSOT=`public API manifest`):
- 用户材料中出现内部导入路径时必须快速失败
- 用户材料中的 `scalim.*` 导入路径必须属于 `manifest` 的 `curated_entrypoints`
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


@dataclass(frozen=True)
class Hit:
    relpath: str
    lineno: int
    kind: str
    token: str
    line: str
    suggestion: str


_TEXT_SUFFIXES: Tuple[str, ...] = (
    ".md",
    ".txt",
    ".py",
    ".yaml",
    ".yml",
    ".toml",
    ".json",
)

_SCALIM_IMPORT_RE = re.compile(r"(?:\bfrom\s+(scalim(?:\.[A-Za-z0-9_]+)*)\s+import\b)|(?:\bimport\s+(scalim(?:\.[A-Za-z0-9_]+)*)\b)")


def _sorted_unique(values: Iterable[str]) -> Tuple[str, ...]:
    return tuple(sorted(set(str(v) for v in values)))


def _load_manifest(path: Path) -> Tuple[Tuple[str, ...], Mapping[str, str]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = "manifest 必须是 JSON object: path={}".format(str(path))
        raise TypeError(msg)

    curated = raw.get("curated_entrypoints")
    if not isinstance(curated, list) or not all(isinstance(x, str) for x in curated):
        msg = "`curated_entrypoints` 必须是字符串列表"
        raise TypeError(msg)
    curated_tuple = tuple(str(x) for x in curated)
    if curated_tuple != _sorted_unique(curated_tuple):
        msg = "`curated_entrypoints` 必须去重并按稳定排序输出"
        raise ValueError(msg)

    internal = raw.get("internal_import_prefix_suggestions", {})
    if not isinstance(internal, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in internal.items()):
        msg = "`internal_import_prefix_suggestions` 必须是字符串映射"
        raise TypeError(msg)

    return curated_tuple, dict(internal)


def _iter_text_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in _TEXT_SUFFIXES:
            continue
        yield path


def _scan_file(
    path: Path,
    *,
    repo_root: Path,
    curated_entrypoints: Tuple[str, ...],
    internal_prefix_suggestions: Mapping[str, str],
) -> List[Hit]:
    rel = str(path.relative_to(repo_root))
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        return [
            Hit(
                relpath=rel,
                lineno=1,
                kind="read-error",
                token="(read-error)",
                line="{}: {}".format(type(exc).__name__, exc),
                suggestion="请检查文件编码或权限.",
            )
        ]

    hits: List[Hit] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        stripped = line.rstrip()

        # 1) 内部/不安全 `token`/`prefix` 门禁(窄且确定)
        for token, suggestion in internal_prefix_suggestions.items():
            if token and token in stripped:
                hits.append(
                    Hit(
                        relpath=rel,
                        lineno=idx,
                        kind="internal",
                        token=token,
                        line=stripped,
                        suggestion=str(suggestion or "").strip() or "请迁移到 `manifest` 中编目的稳定入口.",
                    )
                )

        # 2) `curated_entrypoints` `allowlist` 门禁(仅检查 `scalim.*` 导入)
        match = _SCALIM_IMPORT_RE.search(stripped)
        if not match:
            continue
        module_name = match.group(1) or match.group(2) or ""
        module_name = str(module_name).strip()
        if not module_name:
            continue

        if module_name in curated_entrypoints:
            continue

        suggestion = "请仅从 `manifest` 的 `curated_entrypoints` 导入; 如需新增请更新: `openspec/ssot/public_api_manifest.json`"
        hits.append(
            Hit(
                relpath=rel,
                lineno=idx,
                kind="uncurated",
                token=module_name,
                line=stripped,
                suggestion=suggestion,
            )
        )
    return hits


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="检查 docs/skills 不得引用内部/不安全导入路径.")
    parser.add_argument("--root", default=".", help="仓库根目录(默认: .).")
    parser.add_argument(
        "--manifest",
        default="openspec/ssot/public_api_manifest.json",
        help="public API manifest 路径(默认: openspec/ssot/public_api_manifest.json).",
    )
    parser.add_argument("--docs-root", default="docs/doc", help="文档根目录(默认: docs/doc).")
    parser.add_argument("--notebooks-root", default="notebooks/marimo", help="notebooks 根目录(默认: notebooks/marimo).")
    parser.add_argument("--skills-root", default="artifacts/skills", help="skills 根目录(默认: artifacts/skills).")
    parser.add_argument("--check", action="store_true", help="执行检查; 发现问题时返回非 0 退出码.")
    return parser.parse_args(list(argv))


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    repo_root = Path(str(args.root)).resolve()
    manifest_path = (repo_root / str(args.manifest)).resolve()
    docs_root = (repo_root / str(args.docs_root)).resolve()
    notebooks_root = (repo_root / str(args.notebooks_root)).resolve()
    skills_root = (repo_root / str(args.skills_root)).resolve()

    if not manifest_path.exists():
        print("[错误] `public API manifest` 不存在: {}".format(str(manifest_path)), file=sys.stderr)
        return 2

    try:
        curated_entrypoints, internal_prefix_suggestions = _load_manifest(manifest_path)
    except Exception as exc:  # noqa: BLE001
        print("[错误] `public API manifest` 解析失败: {}: {}".format(type(exc).__name__, exc), file=sys.stderr)
        return 2

    hits: List[Hit] = []
    for root in (docs_root, notebooks_root, skills_root):
        for path in sorted(_iter_text_files(root)):
            hits.extend(
                _scan_file(
                    path,
                    repo_root=repo_root,
                    curated_entrypoints=curated_entrypoints,
                    internal_prefix_suggestions=internal_prefix_suggestions,
                )
            )

    if hits:
        print("[错误] 用户材料导入边界检查失败 ({} 处命中):".format(len(hits)), file=sys.stderr)
        for hit in hits:
            print(
                "- {}:{}: [{}] 命中={!r}: {}".format(hit.relpath, hit.lineno, hit.kind, hit.token, hit.line),
                file=sys.stderr,
            )
            print("  建议: {}".format(hit.suggestion), file=sys.stderr)
        print("", file=sys.stderr)
        print("迁移建议:", file=sys.stderr)
        print("- 优先使用 `manifest` 中的 `curated_entrypoints` 作为稳定导入路径(`SSOT`).", file=sys.stderr)
        print(
            "- 禁止把 `internal/unsafe` 路径写进教程/示例(尤其是 `dsl.by_yaml.runtime.*`/`events._*`/`sinks._internal.*`).",
            file=sys.stderr,
        )
        print("- 若需要新增稳定入口,请先更新 `manifest` 并补齐回归门禁(示例/测试/`just qa`).", file=sys.stderr)
        return 1

    print("[通过] 用户材料导入边界检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
