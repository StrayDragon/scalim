#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# ///
# ruff: noqa: T201
# force-en
"""Scalim core coverage gate (statements + branches).

设计目标:
- 解决“只想对 core 逻辑做 100% 覆盖率门禁,但非 core(如 CLI/展示层/迁移中模块)可显式跳过”的需求.
- 复用现有治理语义: non-core 文件必须显式声明:
  - 文件级: `# pragma: allow-non-core-file <reason>`
- gate 仅对 core 子集做校验:
  - statements(行/语句)覆盖率必须达到阈值
  - branch 覆盖率必须达到阈值

注意:
- 该脚本只“读” coverage JSON,不负责生成覆盖率数据.
- 需要在 pytest-cov/coverage 开启 `--cov-branch` 生成 branch 数据.

用法(示例):
  1) 生成 coverage JSON:
     `uv run pytest tests/ -q -n auto --cov=scalim --cov-branch --cov-report=json:.tmp/coverage.json`
  2) 执行 gate:
     `uv run scripts/check-core-coverage.py --coverage-json .tmp/coverage.json --require-statements 100 --require-branches 100 --check`
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Sequence, Tuple


_ALLOW_NON_CORE_FILE_MARK = "pragma: allow-non-core-file"

_DEFAULT_REL_ROOT = Path("src") / "scalim"
_DEFAULT_COVERAGE_JSON_REL = Path(".tmp") / "coverage.json"
_DEFAULT_TEXT_REPORT_REL = Path(".tmp") / "artifacts" / "core-coverage.report.txt"
_DEFAULT_JSON_REPORT_REL = Path(".tmp") / "artifacts" / "core-coverage.report.json"


@dataclass(frozen=True)
class _NonCoreFile:
    reason: str


@dataclass(frozen=True)
class _CoverageSummary:
    percent_statements_covered: float
    percent_branches_covered: float
    missing_lines: int
    missing_branches: int
    num_partial_branches: int


@dataclass(frozen=True)
class _FailItem:
    path: str
    statements_percent: float
    branches_percent: float
    missing_lines: int
    missing_branches: int
    missing_branch_arcs: Tuple[Tuple[int, int], ...]


def _is_excluded(path: Path) -> bool:
    excluded_parts = {
        ".git",
        ".venv",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        "site",
        "dist",
        "build",
        "node_modules",
        ".tmp",
        "vendor",
    }
    return any(part in excluded_parts for part in path.parts)


def _resolve_input_path(*, repo_root: Path, raw_path: Path) -> Optional[Path]:
    candidate = raw_path if raw_path.is_absolute() else (repo_root / raw_path)
    resolved = candidate.resolve()
    if resolved != repo_root and repo_root not in resolved.parents:
        return None
    rel = resolved.relative_to(repo_root)
    if _is_excluded(rel):
        return None
    return resolved


def _iter_python_files(*, repo_root: Path, rel_root: Path) -> Iterator[Path]:
    root = _resolve_input_path(repo_root=repo_root, raw_path=rel_root)
    if root is None or not root.exists():
        return
    paths = (root,) if root.is_file() else root.rglob("*.py")
    for path in paths:
        if path.suffix != ".py":
            continue
        if path != repo_root and repo_root not in path.parents:
            continue
        rel = path.relative_to(repo_root)
        if _is_excluded(rel):
            continue
        yield path


def _reason_after_marker(text: str, marker: str) -> str:
    if marker not in text:
        return ""
    return text.split(marker, 1)[1].strip()


def _parse_non_core_reason(source: str) -> str:
    """读取文件级 allow-non-core 标记.

    规则:
    - 只在文件 header 注释区生效(模块 docstring 之后/第一段代码之前).
    - 必须带 reason,否则视为未声明.
    """
    in_header = True
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            stripped = token.string.lstrip("#").strip()
            if in_header and _ALLOW_NON_CORE_FILE_MARK in stripped:
                reason = _reason_after_marker(stripped, _ALLOW_NON_CORE_FILE_MARK)
                return reason
            continue

        if token.type in (tokenize.NL, tokenize.NEWLINE, tokenize.ENDMARKER):
            continue
        if token.type == tokenize.STRING and int(token.start[0]) == 1:
            continue
        in_header = False
    return ""


def _classify_files(*, repo_root: Path, rel_root: Path) -> tuple[list[str], dict[str, _NonCoreFile], list[str]]:
    core: list[str] = []
    non_core: dict[str, _NonCoreFile] = {}
    invalid_non_core: list[str] = []

    for abs_path in _iter_python_files(repo_root=repo_root, rel_root=rel_root):
        rel = abs_path.relative_to(repo_root).as_posix()
        source = abs_path.read_text(encoding="utf-8")
        reason = _parse_non_core_reason(source)
        if reason:
            non_core[rel] = _NonCoreFile(reason=reason)
            continue
        if _ALLOW_NON_CORE_FILE_MARK in source:
            # 出现了 marker 但没给 reason: 属于治理错误(避免无理由绕过 gate).
            invalid_non_core.append(rel)
            continue
        core.append(rel)

    return sorted(core), dict(sorted(non_core.items())), sorted(invalid_non_core)


def _load_coverage_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Invalid coverage JSON: expected object at top-level")
    return payload


def _summary_from_file_info(info: Dict[str, Any]) -> _CoverageSummary:
    summary = info.get("summary") or {}
    return _CoverageSummary(
        percent_statements_covered=float(summary.get("percent_statements_covered", 0.0)),
        percent_branches_covered=float(summary.get("percent_branches_covered", 0.0)),
        missing_lines=int(summary.get("missing_lines", 0)),
        missing_branches=int(summary.get("missing_branches", 0)),
        num_partial_branches=int(summary.get("num_partial_branches", 0)),
    )


def _missing_branch_arcs(info: Dict[str, Any]) -> Tuple[Tuple[int, int], ...]:
    arcs = info.get("missing_branches") or []
    if not isinstance(arcs, list):
        return ()
    parsed: list[Tuple[int, int]] = []
    for item in arcs:
        if not isinstance(item, list) or len(item) != 2:
            continue
        a, b = item
        if isinstance(a, int) and isinstance(b, int):
            parsed.append((a, b))
    return tuple(parsed)


def _compute_failures(
    *,
    core_files: Sequence[str],
    coverage_files: Dict[str, Any],
    require_statements: float,
    require_branches: float,
) -> tuple[list[_FailItem], list[str]]:
    failures: list[_FailItem] = []
    missing_in_report: list[str] = []

    for rel in core_files:
        info = coverage_files.get(rel)
        if info is None:
            missing_in_report.append(rel)
            continue
        summary = _summary_from_file_info(info)
        statements_ok = summary.percent_statements_covered >= require_statements
        branches_ok = summary.percent_branches_covered >= require_branches
        if statements_ok and branches_ok:
            continue
        failures.append(
            _FailItem(
                path=rel,
                statements_percent=summary.percent_statements_covered,
                branches_percent=summary.percent_branches_covered,
                missing_lines=summary.missing_lines,
                missing_branches=summary.missing_branches,
                missing_branch_arcs=_missing_branch_arcs(info),
            )
        )

    failures.sort(key=lambda item: (item.statements_percent, item.branches_percent, item.path))
    return failures, missing_in_report


def _render_text_report(
    *,
    coverage_json_path: Path,
    require_statements: float,
    require_branches: float,
    core_files: Sequence[str],
    non_core_files: Dict[str, _NonCoreFile],
    invalid_non_core: Sequence[str],
    failures: Sequence[_FailItem],
    missing_in_report: Sequence[str],
    branch_coverage_enabled: bool,
) -> str:
    lines = [
        "core-coverage gate report",
        "",
        "inputs:",
        "  coverage_json={}".format(coverage_json_path.as_posix()),
        "  require_statements={}".format(require_statements),
        "  require_branches={}".format(require_branches),
        "",
        "core selection:",
        "  core_files={}".format(len(core_files)),
        "  non_core_files={}".format(len(non_core_files)),
        "  invalid_non_core={}".format(len(invalid_non_core)),
        "",
        "coverage meta:",
        "  branch_coverage_enabled={}".format(branch_coverage_enabled),
        "",
        "result:",
        "  failures={}".format(len(failures)),
        "  missing_in_report={}".format(len(missing_in_report)),
    ]

    if invalid_non_core:
        lines.extend(["", "invalid non-core markers (missing reason):"])
        for rel in invalid_non_core[:50]:
            lines.append("  - {}".format(rel))
        if len(invalid_non_core) > 50:
            lines.append("  ... ({} more)".format(len(invalid_non_core) - 50))

    if missing_in_report:
        lines.extend(["", "core files missing in coverage report:"])
        for rel in missing_in_report[:50]:
            lines.append("  - {}".format(rel))
        if len(missing_in_report) > 50:
            lines.append("  ... ({} more)".format(len(missing_in_report) - 50))

    if failures:
        lines.extend(["", "failures:"])
        for item in failures[:200]:
            lines.append(
                "  - {} statements={:.2f}% branches={:.2f}% missing_lines={} missing_branches={}".format(
                    item.path,
                    item.statements_percent,
                    item.branches_percent,
                    item.missing_lines,
                    item.missing_branches,
                )
            )
            if item.missing_branch_arcs:
                preview = ", ".join("{}->{}".format(a, b) for a, b in item.missing_branch_arcs[:12])
                suffix = " ..." if len(item.missing_branch_arcs) > 12 else ""
                lines.append("      missing_branch_arcs: {}{}".format(preview, suffix))
        if len(failures) > 200:
            lines.append("  ... ({} more)".format(len(failures) - 200))

    if non_core_files:
        lines.extend(["", "non-core files (explicit allow markers):"])
        for rel, meta in list(non_core_files.items())[:100]:
            lines.append("  - {} reason={}".format(rel, meta.reason))
        if len(non_core_files) > 100:
            lines.append("  ... ({} more)".format(len(non_core_files) - 100))

    lines.append("")
    return "\n".join(lines)


def _render_json_report(
    *,
    coverage_json_path: Path,
    require_statements: float,
    require_branches: float,
    core_files: Sequence[str],
    non_core_files: Dict[str, _NonCoreFile],
    invalid_non_core: Sequence[str],
    failures: Sequence[_FailItem],
    missing_in_report: Sequence[str],
    branch_coverage_enabled: bool,
) -> str:
    payload = {
        "inputs": {
            "coverage_json": coverage_json_path.as_posix(),
            "require_statements": require_statements,
            "require_branches": require_branches,
        },
        "core_selection": {
            "core_files": list(core_files),
            "non_core_files": {rel: {"reason": meta.reason} for rel, meta in non_core_files.items()},
            "invalid_non_core": list(invalid_non_core),
        },
        "coverage_meta": {
            "branch_coverage_enabled": bool(branch_coverage_enabled),
        },
        "result": {
            "failures": [
                {
                    "path": item.path,
                    "statements_percent": item.statements_percent,
                    "branches_percent": item.branches_percent,
                    "missing_lines": item.missing_lines,
                    "missing_branches": item.missing_branches,
                    "missing_branch_arcs": list(item.missing_branch_arcs),
                }
                for item in failures
            ],
            "missing_in_report": list(missing_in_report),
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Core coverage gate (statements + branches).")
    parser.add_argument("--root", default=str(_DEFAULT_REL_ROOT), help="扫描 core/non-core 的根目录(默认: src/scalim).")
    parser.add_argument(
        "--coverage-json",
        default=str(_DEFAULT_COVERAGE_JSON_REL),
        help="coverage json 路径(默认: .tmp/coverage.json).",
    )
    parser.add_argument("--require-statements", type=float, required=True, help="core statements 覆盖率阈值(0-100).")
    parser.add_argument("--require-branches", type=float, required=True, help="core branch 覆盖率阈值(0-100).")
    parser.add_argument("--json", action="store_true", help="输出 JSON 报告.")
    parser.add_argument("--report", default="", help="覆盖默认文本报告路径.")
    parser.add_argument("--no-artifacts", action="store_true", help="不自动写入 `.tmp/artifacts/core-coverage.report.{txt,json}`.")
    parser.add_argument("--check", action="store_true", help="若 gate 失败则返回非零退出码.")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    rel_root = Path(str(args.root))
    coverage_json_path = Path(str(args.coverage_json))
    coverage_json_abs = (coverage_json_path if coverage_json_path.is_absolute() else repo_root / coverage_json_path).resolve()

    if not coverage_json_abs.exists():
        raise SystemExit("[error] coverage json not found: {}".format(coverage_json_abs.as_posix()))

    core_files, non_core_files, invalid_non_core = _classify_files(repo_root=repo_root, rel_root=rel_root)

    payload = _load_coverage_json(coverage_json_abs)
    meta = payload.get("meta") or {}
    branch_coverage_enabled = bool(meta.get("branch_coverage"))
    coverage_files = payload.get("files") or {}
    if not isinstance(coverage_files, dict):
        raise ValueError("Invalid coverage JSON: files must be a dict")

    failures, missing_in_report = _compute_failures(
        core_files=core_files,
        coverage_files=coverage_files,
        require_statements=float(args.require_statements),
        require_branches=float(args.require_branches),
    )

    text_report = _render_text_report(
        coverage_json_path=coverage_json_abs,
        require_statements=float(args.require_statements),
        require_branches=float(args.require_branches),
        core_files=core_files,
        non_core_files=non_core_files,
        invalid_non_core=invalid_non_core,
        failures=failures,
        missing_in_report=missing_in_report,
        branch_coverage_enabled=branch_coverage_enabled,
    )
    json_report = _render_json_report(
        coverage_json_path=coverage_json_abs,
        require_statements=float(args.require_statements),
        require_branches=float(args.require_branches),
        core_files=core_files,
        non_core_files=non_core_files,
        invalid_non_core=invalid_non_core,
        failures=failures,
        missing_in_report=missing_in_report,
        branch_coverage_enabled=branch_coverage_enabled,
    )
    output = json_report if args.json else text_report

    if not args.no_artifacts:
        text_report_path = _DEFAULT_TEXT_REPORT_REL if not args.report else Path(args.report)
        text_report_abs = (text_report_path if text_report_path.is_absolute() else repo_root / text_report_path).resolve()
        json_report_abs = (repo_root / _DEFAULT_JSON_REPORT_REL).resolve()
        text_report_abs.parent.mkdir(parents=True, exist_ok=True)
        json_report_abs.parent.mkdir(parents=True, exist_ok=True)
        text_report_abs.write_text(text_report, encoding="utf-8")
        json_report_abs.write_text(json_report, encoding="utf-8")
    elif args.report:
        report_path = (Path(args.report) if Path(args.report).is_absolute() else repo_root / args.report).resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(text_report, encoding="utf-8")

    sys.stdout.write(output)

    hard_fail = False
    if invalid_non_core:
        hard_fail = True
    if missing_in_report:
        hard_fail = True
    if failures:
        hard_fail = True
    if float(args.require_branches) > 0 and not branch_coverage_enabled:
        hard_fail = True

    if args.check and hard_fail:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
