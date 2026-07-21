#!/usr/bin/env python3
"""公开 API 覆盖报告：每个 ``**/__init__.py`` re-export 入口被多少 notebook 覆盖。

类比 ``pytest-cov``：入口 = 源码行，notebook = 测试用例。报告回答「每个入口的覆盖度」。

默认输出 CSV，也可选终端可读报告。

用法：
  python scripts/report-notebooks-coverage.py                 # CSV 输出
  python scripts/report-notebooks-coverage.py --report        # 终端可读报告
  python scripts/report-notebooks-coverage.py --check         # gate 模式(聚合)
  python scripts/report-notebooks-coverage.py --min-pct 20    # 每入口需 ≥20% notebook 覆盖
  python scripts/report-notebooks-coverage.py --check --quiet # gate + 通过时静默
  python scripts/report-notebooks-coverage.py --json          # 结构化输出
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _discover_notebooks(marimo_root: Path) -> Dict[str, List[Path]]:
    """发现所有套件中的章节 notebook,按套件分组。"""
    suites: Dict[str, List[Path]] = {}
    for suite_dir_name in sorted(marimo_root.iterdir(), key=lambda p: p.name):
        if not suite_dir_name.is_dir():
            continue
        suite_name = suite_dir_name.name
        chapter_files: List[Path] = []
        for sub in suite_dir_name.iterdir():
            if not sub.is_dir() or not sub.name.startswith("chapters"):
                continue
            if not (sub / "registry.py").is_file():
                continue
            for py_file in sorted(sub.glob("ch*.py"), key=lambda p: p.name):
                if py_file.name == "registry.py":
                    continue
                chapter_files.append(py_file)
        if chapter_files:
            suites[suite_name] = chapter_files
    return suites


def _parse_entrypoints(repo_root: Path) -> Tuple[str, ...]:
    """从 scalim 源码中提取所有 ``**/__init__.py`` re-export 入口模块名。

    入口由 ``# pragma: scalim-public-api tier1:...`` 标记定义。
    """
    marker_re = re.compile(
        r"^#\s*pragma:\s*scalim-public-api\s+tier(?P<tier>\d+):(?P<order>\d+):(?P<module>[A-Za-z0-9_\\.]+)\|",
        flags=re.IGNORECASE,
    )
    modules: Dict[int, str] = {}
    scan_root = repo_root / "src" / "scalim"
    for py_file in sorted(scan_root.rglob("__init__.py")):
        try:
            text = py_file.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            m = marker_re.match(line.strip())
            if m:
                order = int(m.group("order"))
                modules[order] = m.group("module")
    return tuple(modules[order] for order in sorted(modules))


def _extract_imports(path: Path) -> Set[str]:
    """提取 Python 文件中所有 ``scalim.*`` 导入路径。"""
    import ast

    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return set()

    candidates: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = str(getattr(alias, "name", "") or "")
                if name.startswith("scalim"):
                    candidates.add(name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue
            mod = str(getattr(node, "module", "") or "")
            if not mod.startswith("scalim"):
                continue
            candidates.add(mod)
            for alias in node.names:
                child = str(getattr(alias, "name", "") or "")
                if child and child != "*":
                    candidates.add(f"{mod}.{child}")
    return candidates


def _compute_entrypoint_coverage(
    suites: Dict[str, List[Path]],
    entrypoints: Tuple[str, ...],
) -> Dict[str, Any]:
    """入口视角覆盖：每个入口被哪些 notebook 覆盖。"""
    total_notebooks = sum(len(nbs) for nbs in suites.values())

    # ep → set of notebook names
    ep_to_notebooks: Dict[str, Set[str]] = OrderedDict((e, set()) for e in entrypoints)

    for suite_name, notebooks in suites.items():
        for nb_path in notebooks:
            nb_name = f"{suite_name}/{nb_path.name}"
            imports = _extract_imports(nb_path)
            for imp in imports:
                parts = imp.split(".")
                for end in range(1, len(parts) + 1):
                    prefix = ".".join(parts[:end])
                    if prefix in ep_to_notebooks:
                        ep_to_notebooks[prefix].add(nb_name)

    entrypoint_rows: List[Dict[str, Any]] = []
    for ep, nbs in ep_to_notebooks.items():
        entrypoint_rows.append(
            {
                "entrypoint": ep,
                "covered_count": len(nbs),
                "coverage_pct": round(len(nbs) / total_notebooks * 100, 1),
                "notebooks": sorted(nbs),
            }
        )

    uncovered = [e["entrypoint"] for e in entrypoint_rows if e["covered_count"] == 0]
    pcts = [e["coverage_pct"] for e in entrypoint_rows]
    avg_pct = round(sum(pcts) / len(pcts), 1) if pcts else 0.0

    return {
        "total_notebooks": total_notebooks,
        "total_entrypoints": len(entrypoints),
        "uncovered": uncovered,
        "average_coverage_pct": avg_pct,
        "entrypoints": entrypoint_rows,
    }


def _print_csv(data: Dict[str, Any]) -> None:
    """CSV 输出：每行一个入口，列=entrypoint, covered_count, coverage_pct, notebooks。"""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["entrypoint", "covered_count", "coverage_pct", "notebooks"])
    for ep in data["entrypoints"]:
        writer.writerow(
            [
                ep["entrypoint"],
                ep["covered_count"],
                ep["coverage_pct"],
                ";".join(ep["notebooks"]),
            ]
        )
    writer.writerow(
        [
            "(summary: average coverage)",
            "",
            data["average_coverage_pct"],
            f"total_notebooks={data['total_notebooks']} uncovered={len(data['uncovered'])}",
        ]
    )
    sys.stdout.write(out.getvalue())


def _print_report(data: Dict[str, Any]) -> None:
    """人类可读的终端报告。"""
    total = data["total_notebooks"]
    label = "**/__init__.py re-export 入口"
    print(f"每个 {label} 被多少 notebook 覆盖 (共 {total} 个 notebook)")
    print(f"平均覆盖率: {data['average_coverage_pct']:.0f}%")
    if data["uncovered"]:
        print(f"未覆盖入口: {', '.join(data['uncovered'])}")
    print()

    for ep in data["entrypoints"]:
        n = ep["covered_count"]
        pct = ep["coverage_pct"]
        bar_len = int(pct / 5)
        bar = "█" * bar_len
        print(f"  {pct:5.0f}%  {bar:20s}  {ep['entrypoint']}")


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="``**/__init__.py`` re-export 入口 → notebook 覆盖报告")
    p.add_argument("--quiet", action="store_true", help="静默模式: 通过时不写 stdout (失败仍写 stderr)")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    p.add_argument("--report", action="store_true", help="输出终端可读报告 (默认: CSV)")
    p.add_argument("--check", action="store_true", help="gate 模式(聚合): 存在零覆盖入口时非零退出")
    p.add_argument(
        "--min-pct",
        type=float,
        default=None,
        metavar="PCT",
        help="每个入口的最低覆盖率阈值(如 --min-pct 20 要求每入口 ≥20%% notebook 覆盖)",
    )
    p.add_argument(
        "--entries",
        action="store_true",
        help="同时输出每个入口被哪些具体 notebook 覆盖 (CSV/报告模式下展开)",
    )
    return p.parse_args(list(argv or sys.argv[1:]))


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    root = _repo_root()
    marimo_root = root / "notebooks" / "marimo"

    entrypoints = _parse_entrypoints(root)
    suites = _discover_notebooks(marimo_root)
    data = _compute_entrypoint_coverage(suites, entrypoints)
    total = data["total_notebooks"]

    if args.json:
        json.dump(data, sys.stdout, indent=2, ensure_ascii=False, default=str)
        print()
        return 0

    label = "**/__init__.py re-export 入口"

    if args.check:
        if data["uncovered"]:
            sys.stderr.write(f"{len(data['uncovered'])} 个 {label} 零覆盖:\n")
            for ep in data["uncovered"]:
                sys.stderr.write(f"  {ep}\n")
            return 1
        if not args.quiet:
            print(f"✓ 全部 {len(entrypoints)} 个 {label} 已被至少 1 个 notebook 覆盖")
        return 0

    if args.min_pct is not None:
        threshold = float(args.min_pct)
        failures = [(ep["entrypoint"], ep["coverage_pct"]) for ep in data["entrypoints"] if ep["coverage_pct"] < threshold]
        if failures:
            sys.stderr.write(f"{len(failures)} 个 {label} 覆盖率低于 {threshold:.0f}%:\n")
            for ep_name, pct in failures:
                sys.stderr.write(f"  {ep_name}: {pct:.0f}%\n")
            return 1
        if not args.quiet:
            print(f"✓ 全部 {len(entrypoints)} 个 {label} 覆盖率 ≥ {threshold:.0f}%")
        return 0

    if args.entries:
        # 展开模式：每个入口列出覆盖它的 notebook
        for ep in data["entrypoints"]:
            print(f"{ep['entrypoint']}: {ep['coverage_pct']:.0f}% ({ep['covered_count']}/{total})")
            for nb in ep["notebooks"]:
                print(f"  - {nb}")
            print()
        return 0

    verbose = os.environ.get("QA_VERBOSE", "").strip().lower() in ("1", "true", "yes", "on")
    if verbose or args.report:
        _print_report(data)
    else:
        _print_csv(data)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
