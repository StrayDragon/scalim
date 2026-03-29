#!/usr/bin/env python3
"""检查 `public API manifest` 与运行时 `__all__` 是否一致.

用途:
- 将 `public API manifest` 作为“稳定公开入口”的单一事实来源(`SSOT`)
- 在 `just qa` 中快速失败,阻止“静默扩大/缩小公开面”

校验内容:
- `manifest` 文件本身的稳定性约束(去重/排序)
- `stable_modules` 中每个模块的 `__all__` 与 `manifest` 精确一致(集合一致)
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


@dataclass(frozen=True)
class _Manifest:
    stable_modules: Mapping[str, Tuple[str, ...]]
    curated_entrypoints: Tuple[str, ...]
    internal_prefix_suggestions: Mapping[str, str]


def _sorted_unique_tuple(values: Iterable[str]) -> Tuple[str, ...]:
    return tuple(sorted(set(str(v) for v in values)))


def _load_manifest(path: Path) -> _Manifest:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = "manifest 必须是 JSON object: path={}".format(str(path))
        raise TypeError(msg)

    schema_version = raw.get("schema_version")
    if schema_version != 1:
        msg = "manifest schema_version 不支持(仅支持 1): got={}".format(schema_version)
        raise ValueError(msg)

    curated = raw.get("curated_entrypoints")
    if not isinstance(curated, list) or not all(isinstance(x, str) for x in curated):
        msg = "`curated_entrypoints` 必须是字符串列表"
        raise TypeError(msg)
    curated_tuple = tuple(str(x) for x in curated)
    if curated_tuple != _sorted_unique_tuple(curated_tuple):
        msg = "`curated_entrypoints` 必须去重并按稳定排序输出"
        raise ValueError(msg)

    stable = raw.get("stable_modules")
    if not isinstance(stable, dict) or not all(isinstance(k, str) for k in stable):
        msg = "`stable_modules` 必须是 module->exports 的映射"
        raise TypeError(msg)

    stable_modules: Dict[str, Tuple[str, ...]] = {}
    for module_name, exports in stable.items():
        if not isinstance(exports, list) or not all(isinstance(x, str) for x in exports):
            msg = "`stable_modules['{}']` 必须是字符串列表".format(module_name)
            raise TypeError(msg)
        exports_tuple = tuple(str(x) for x in exports)
        if exports_tuple != _sorted_unique_tuple(exports_tuple):
            msg = "`stable_modules['{}']` 的导出列表必须去重并按稳定排序输出".format(module_name)
            raise ValueError(msg)
        stable_modules[str(module_name)] = exports_tuple

    stable_keys = tuple(stable_modules.keys())
    if stable_keys != tuple(sorted(stable_keys)):
        msg = "`stable_modules` 的模块名必须按稳定排序输出"
        raise ValueError(msg)

    internal_suggestions = raw.get("internal_import_prefix_suggestions", {})
    if not isinstance(internal_suggestions, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in internal_suggestions.items()
    ):
        msg = "`internal_import_prefix_suggestions` 必须是字符串映射"
        raise TypeError(msg)

    missing_in_curated = tuple(sorted(set(stable_modules.keys()) - set(curated_tuple)))
    if missing_in_curated:
        msg = "`stable_modules` 必须是 `curated_entrypoints` 的子集; 缺失: {}".format(", ".join(missing_in_curated))
        raise ValueError(msg)

    return _Manifest(
        stable_modules=dict(stable_modules),
        curated_entrypoints=curated_tuple,
        internal_prefix_suggestions=dict(internal_suggestions),
    )


def _extract_declared_all(module: Any) -> Tuple[str, ...]:
    declared = getattr(module, "__all__", None)
    if declared is None:
        msg = "模块未定义 `__all__`: module={}".format(str(getattr(module, "__name__", type(module).__name__)))
        raise ValueError(msg)
    if not isinstance(declared, (list, tuple)) or not all(isinstance(x, str) for x in declared):
        msg = "`__all__` 必须是字符串列表/元组: module={}".format(str(getattr(module, "__name__", type(module).__name__)))
        raise TypeError(msg)
    return tuple(str(x) for x in declared)


def _compare_all(*, module_name: str, expected: Set[str], declared: Set[str]) -> Optional[str]:
    missing = tuple(sorted(expected - declared))
    stale = tuple(sorted(declared - expected))
    if not missing and not stale:
        return None
    parts: List[str] = []
    if missing:
        parts.append("missing={}".format(", ".join(missing)))
    if stale:
        parts.append("stale={}".format(", ".join(stale)))
    return "{}: __all__ mismatch ({})".format(module_name, "; ".join(parts))


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="检查 `public API manifest` 与 `__all__` 是否一致.")
    parser.add_argument(
        "--manifest",
        default="openspec/ssot/public_api_manifest.json",
        help="`manifest` `JSON` 文件路径(默认: openspec/ssot/public_api_manifest.json).",
    )
    parser.add_argument("--check", action="store_true", help="执行检查;失败返回非 0.")
    return parser.parse_args(list(argv))


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    manifest_path = Path(str(args.manifest)).resolve()
    if not manifest_path.exists():
        print("[错误] `manifest` 不存在: {}".format(str(manifest_path)), file=sys.stderr)
        return 2

    try:
        manifest = _load_manifest(manifest_path)
    except Exception as exc:  # noqa: BLE001
        print("[错误] `manifest` 解析失败: {}: {}".format(type(exc).__name__, exc), file=sys.stderr)
        return 2

    failures: List[str] = []
    for module_name, exports in manifest.stable_modules.items():
        try:
            mod = importlib.import_module(module_name)
        except Exception as exc:  # noqa: BLE001
            failures.append("{}: 导入失败: {}: {}".format(module_name, type(exc).__name__, exc))
            continue

        try:
            declared_all = _extract_declared_all(mod)
        except Exception as exc:  # noqa: BLE001
            failures.append("{}: `__all__` 非法: {}: {}".format(module_name, type(exc).__name__, exc))
            continue

        mismatch = _compare_all(module_name=module_name, expected=set(exports), declared=set(declared_all))
        if mismatch:
            failures.append(mismatch)

    if failures:
        print("[错误] `public API manifest` 校验失败 ({} 项):".format(len(failures)), file=sys.stderr)
        for item in failures:
            print("- {}".format(item), file=sys.stderr)
        print("\n修复建议:", file=sys.stderr)
        print("1) 若公开面变更是预期的: 同步更新 `manifest` 与相关回归(示例/测试/`just qa`).", file=sys.stderr)
        print("2) 若不是预期的: 回退导出变化或收敛到稳定 `facade`.", file=sys.stderr)
        return 1

    print("[通过] `public API manifest` 校验通过: stable_modules={}".format(len(manifest.stable_modules)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
