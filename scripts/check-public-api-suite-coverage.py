#!/usr/bin/env python3
"""检查 `Tier1 curated entrypoints` 与 `public API` 示例/`pytest` 覆盖的一致性.

本门禁目标: `fail-fast`。当 `Tier1 public surface` 漂移时,必须同步补齐示例章节与 `pytest public_api` 回归,
否则 `just qa` 会在 `pytest` 前阶段失败退出.

`SSOT`:
  - `Tier1 curated entrypoints`:
      `src/scalim/**/__init__.py` 中的标记:
      `# pragma: scalim-public-api tier1:<order>:<module>|<desc>|<scenario>`
  - 示例章节覆盖:
      `notebooks/marimo/example_public_api_suite/chapters/*.py` 的静态扫描覆盖集合
  - `pytest public_api` 覆盖:
      `tests/public_api/test_example_public_api_suite.py` 中的 `chapter_ids=[...]`

约束:
  - 静态扫描(仅 `AST`/文本),不执行 `notebooks`,不 `import` `scalim` 模块。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, List, Sequence, Set

from public_api_tooling import PublicApiProblem, discover_public_api_entrypoints, repo_root_for_script
from scalim_misc.public_api_suite_coverage import (
    CoverageError,
    build_tier1_coverage_for_examples_suite,
    parse_public_api_pytest_chapter_ids,
)


def _as_relpath(path: Path, *, repo_root: Path) -> str:
    try:
        rel = path.relative_to(repo_root)
    except ValueError:
        return str(path)
    return str(rel).replace("\\", "/")


def _format_modules(modules: Iterable[str]) -> str:
    return "\n".join("- {}".format(m) for m in sorted(set(modules)))


def _format_problems(problems: Sequence[PublicApiProblem], *, repo_root: Path) -> str:
    lines: List[str] = []
    for p in problems:
        rel = _as_relpath(p.path, repo_root=repo_root) if p.path.exists() else str(p.path)
        module = str(p.module or "(unknown)")
        lines.append("- {}:{}: {}: {}".format(rel, int(p.lineno), module, p.reason))
    return "\n".join(lines)


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Tier1 public API coverage drift for examples/pytest suites.")
    parser.add_argument("--check", action="store_true", help="Fail with non-zero exit code when drift is detected.")
    return parser.parse_args(list(argv))


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    repo_root = repo_root_for_script(Path(__file__))

    entrypoints, marker_problems = discover_public_api_entrypoints(repo_root, tier=1)
    tier1_modules: Set[str] = {e.module for e in entrypoints}

    failures: List[str] = []
    if marker_problems:
        failures.append("[错误] Tier1 curated entrypoints 标记存在问题:\n{}".format(_format_problems(marker_problems, repo_root=repo_root)))

    if not tier1_modules:
        failures.append("[错误] 未发现 Tier1 curated entrypoints (tier1 markers).")

    try:
        examples_coverage = build_tier1_coverage_for_examples_suite(repo_root, tier1_modules)
    except CoverageError as exc:
        examples_coverage = None
        failures.append("[错误] examples suite 覆盖扫描失败: {}".format(exc))

    try:
        pytest_chapter_ids = parse_public_api_pytest_chapter_ids(repo_root)
        pytest_coverage = build_tier1_coverage_for_examples_suite(repo_root, tier1_modules, chapter_ids=pytest_chapter_ids)
    except CoverageError as exc:
        pytest_chapter_ids = ()
        pytest_coverage = None
        failures.append("[错误] pytest public_api suite 覆盖扫描失败: {}".format(exc))

    if examples_coverage is not None:
        missing_in_examples = sorted(tier1_modules.difference(examples_coverage.covered_modules))
        if missing_in_examples:
            failures.append(
                "[错误] Tier1 入口未被 examples suite 覆盖 (缺失 {} 项):\n{}\n\n修复:\n"
                "- 新增/补齐章节: `notebooks/marimo/example_public_api_suite/chapters/`\n"
                "- 验证: `just examples`".format(len(missing_in_examples), _format_modules(missing_in_examples))
            )

    if pytest_coverage is not None:
        missing_in_pytest = sorted(tier1_modules.difference(pytest_coverage.covered_modules))
        if missing_in_pytest:
            failures.append(
                "[错误] Tier1 入口未被 pytest public_api suite 覆盖 (缺失 {} 项):\n{}\n\n修复:\n"
                "- 更新 `tests/public_api/test_example_public_api_suite.py` 的 `chapter_ids=[...]`\n"
                "- 验证: `pytest -q tests/public_api/ --no-cov`".format(len(missing_in_pytest), _format_modules(missing_in_pytest))
            )

    if examples_coverage is not None and pytest_coverage is not None:
        examples_tier1 = set(examples_coverage.covered_modules)
        pytest_tier1 = set(pytest_coverage.covered_modules)
        drift_examples_only = sorted(examples_tier1.difference(pytest_tier1))
        drift_pytest_only = sorted(pytest_tier1.difference(examples_tier1))
        if drift_examples_only or drift_pytest_only:
            parts: List[str] = []
            if drift_examples_only:
                parts.append("仅 examples 覆盖:\n{}".format(_format_modules(drift_examples_only)))
            if drift_pytest_only:
                parts.append("仅 pytest 覆盖:\n{}".format(_format_modules(drift_pytest_only)))
            failures.append(
                "[错误] examples suite 与 pytest public_api suite 在 Tier1 范围内覆盖集合不一致:\n{}\n\n修复:\n"
                "- 章节补齐后,同步更新 pytest 的 `chapter_ids` 选择\n"
                "- 验证: `just qa` (fail-fast before pytest)".format("\n\n".join(parts))
            )

    if failures:
        sys.stderr.write("\n\n".join(failures))
        sys.stderr.write("\n")
        return 1 if args.check else 0

    sys.stdout.write("[通过] 第 1 层入口 ↔ 示例 ↔ `pytest` 覆盖一致\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
