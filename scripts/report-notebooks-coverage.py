#!/usr/bin/env python3
"""Tier1 公开 API 覆盖报告：统计每个 notebook 导入了多少 Tier1 入口模块。

默认输出 CSV（人类可读 + 机器可解析），也可选纯终端报告。

用法：
  python scripts/report-notebooks-coverage.py           # CSV 输出
  python scripts/report-notebooks-coverage.py --report  # 终端可读报告
  python scripts/report-notebooks-coverage.py --check   # gate 模式
  python scripts/report-notebooks-coverage.py --json    # 结构化输出
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
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
        # 方案: chapters/ 直接子目录 或 chapters_of_*/ 模式
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


def _parse_tier1_modules(repo_root: Path) -> Tuple[str, ...]:
    """从 scalim 源码中提取所有 Tier1 public API 入口模块名。"""
    import ast
    import re

    marker_re = re.compile(
        r"^#\s*pragma:\s*scalim-public-api\s+tier(?P<tier>\d+):(?P<order>\d+):(?P<module>[A-Za-z0-9_\\.]+)\|",
        flags=re.IGNORECASE,
    )
    modules: Dict[int, str] = {}  # order -> module

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
    """提取 Python 文件中所有 `scalim.*` 导入路径。"""
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


def _match_to_tier1(imports: Set[str], tier1: Set[str]) -> Tuple[Set[str], Set[str]]:
    """将 import 集合映射到 Tier1 入口,返回 (已覆盖, 未覆盖)。"""
    covered: Set[str] = set()
    for imp in imports:
        parts = imp.split(".")
        for end in range(1, len(parts) + 1):
            prefix = ".".join(parts[:end])
            if prefix in tier1:
                covered.add(prefix)
    missing = tier1 - covered
    return covered, missing


def _compute_coverage(
    suites: Dict[str, List[Path]],
    tier1: Tuple[str, ...],
    root: Path,
) -> Dict[str, Any]:
    """计算全部套件的覆盖率数据。"""
    tier1_set = set(tier1)
    all_covered: Set[str] = set()
    suite_results: Dict[str, Any] = {}
    marimo_root = root / "notebooks" / "marimo"

    for suite_name, notebooks in suites.items():
        nb_results: List[Dict[str, Any]] = []
        suite_covered: Set[str] = set()
        for nb_path in notebooks:
            imports = _extract_imports(nb_path)
            covered, missing = _match_to_tier1(imports, tier1_set)
            suite_covered.update(covered)
            nb_results.append({
                "notebook": str(nb_path.relative_to(marimo_root)),
                "covered": sorted(covered),
                "missing": sorted(missing),
                "coverage_pct": round(len(covered) / len(tier1_set) * 100, 1),
            })
        all_covered.update(suite_covered)
        suite_results[suite_name] = {
            "notebooks": nb_results,
            "suite_covered": len(suite_covered),
            "suite_total": len(tier1_set),
            "suite_pct": round(len(suite_covered) / len(tier1_set) * 100, 1),
        }

    return {
        "tier1_modules": list(tier1),
        "tier1_count": len(tier1),
        "aggregate_covered": sorted(all_covered),
        "aggregate_missing": sorted(tier1_set - all_covered),
        "aggregate_pct": round(len(all_covered) / len(tier1_set) * 100, 1),
        "suites": suite_results,
    }


def _print_csv(data: Dict[str, Any]) -> None:
    """CSV 输出：每行一个 notebook，列=suite, notebook, covered, covered_pct, missing。"""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["suite", "notebook", "covered_count", "coverage_pct", "covered_modules", "missing_modules"])
    for suite_name, suite in data["suites"].items():
        for nb in suite["notebooks"]:
            writer.writerow([
                suite_name,
                nb["notebook"].rsplit("/", 1)[-1],
                len(nb["covered"]),
                nb["coverage_pct"],
                ";".join(nb["covered"]),
                ";".join(nb["missing"]),
            ])
        # 套件汇总行
        writer.writerow([
            suite_name,
            "(suite aggregate)",
            suite["suite_covered"],
            suite["suite_pct"],
            "",
            "",
        ])
    # 全局汇总行
    writer.writerow([
        "(all suites)",
        "(aggregate)",
        len(data["aggregate_covered"]),
        data["aggregate_pct"],
        ";".join(data["aggregate_covered"]),
        ";".join(data["aggregate_missing"]),
    ])
    sys.stdout.write(out.getvalue())


def _print_report(data: Dict[str, Any]) -> None:
    """人类可读的终端报告。"""
    print(f"Tier1 公开 API 入口 ({data['tier1_count']} 个)")
    print(f"全量覆盖: {len(data['aggregate_covered'])}/{data['tier1_count']} ({data['aggregate_pct']}%)")
    if data["aggregate_missing"]:
        print(f"未覆盖: {', '.join(data['aggregate_missing'])}")
    print()

    for suite_name, suite in data["suites"].items():
        print(f"── {suite_name} ({suite['suite_covered']}/{suite['suite_total']}, {suite['suite_pct']}%)")
        for nb in suite["notebooks"]:
            print(f"   {nb['coverage_pct']:5.0f}%  {nb['notebook'].rsplit('/', 1)[-1]:45s}  covered={len(nb['covered'])}"
                  f"{'  MISSING: ' + ','.join(nb['missing'][:3]) + ('...' if len(nb['missing']) > 3 else '') if nb['missing'] else ''}")


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Tier1 公开 API 覆盖报告")
    p.add_argument("--check", action="store_true", help="gate 模式: 存在未覆盖入口时非零退出")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    p.add_argument("--report", action="store_true", help="输出终端可读报告(默认: CSV)")
    p.add_argument("--min-pct", type=float, default=0.0, help="最低聚合覆盖率阈值 (默认 0%%, 即不强制)")
    return p.parse_args(list(argv or sys.argv[1:]))


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    root = _repo_root()
    marimo_root = root / "notebooks" / "marimo"

    tier1 = _parse_tier1_modules(root)
    suites = _discover_notebooks(marimo_root)
    data = _compute_coverage(suites, tier1, root)

    if args.json:
        json.dump(data, sys.stdout, indent=2, ensure_ascii=False, default=str)
        print()
        return 0

    if args.report:
        _print_report(data)
    else:
        _print_csv(data)

    if args.check:
        if data["aggregate_pct"] < args.min_pct:
            sys.stderr.write(f"\n覆盖率 {data['aggregate_pct']}% 低于阈值 {args.min_pct}%\n")
            return 1
        if data["aggregate_missing"]:
            sys.stderr.write(f"\n存在 {len(data['aggregate_missing'])} 个未覆盖的 Tier1 入口\n")
            return 1
        print("\n✓ 全部 Tier1 入口已被至少一个 notebook 覆盖")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
