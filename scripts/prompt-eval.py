# ruff: noqa: T201
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

_RUNNER_NAME = "prompt-eval"
_RUNNER_VERSION = "0.1.0"

_AUTOGEN_BEGIN_RE = re.compile(r"<!--\s*BEGIN AUTOGEN:([A-Za-z0-9_.-]+)\s*-->")
_AUTOGEN_END_RE = re.compile(r"<!--\s*END AUTOGEN:([A-Za-z0-9_.-]+)\s*-->")

_DIFF_FILE_RE = re.compile(r"^diff --git a/(.+) b/(.+)$")
_DIFF_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def _safe_rmtree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def _git_head(root: Path) -> Optional[str]:
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(root))
    except Exception:
        return None
    value = out.decode("utf-8", errors="ignore").strip()
    return value or None


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    path: Optional[str] = None
    line: Optional[int] = None

    def as_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"code": self.code, "message": self.message}
        if self.path is not None:
            payload["path"] = self.path
        if self.line is not None:
            payload["line"] = self.line
        return payload


@dataclass(frozen=True)
class Case:
    case_id: str
    title: str
    kind: str
    inputs: Dict[str, Any]
    expect: Dict[str, Any]
    case_dir: Path


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    title: str
    kind: str
    ok: bool
    expected_ok: bool
    observed_ok: bool
    violations: Tuple[Issue, ...]
    issues: Tuple[Issue, ...]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.case_id,
            "title": self.title,
            "kind": self.kind,
            "ok": self.ok,
            "expected_ok": self.expected_ok,
            "observed_ok": self.observed_ok,
            "violations": [i.as_dict() for i in self.violations],
            "issues": [i.as_dict() for i in self.issues],
        }


@dataclass(frozen=True)
class DiffHunk:
    old_start: int
    new_start: int
    lines: Tuple[str, ...]


@dataclass(frozen=True)
class FilePatch:
    old_path: str
    new_path: str
    hunks: Tuple[DiffHunk, ...]

    def paths(self) -> Tuple[str, str]:
        return (self.old_path, self.new_path)


def _load_case(path: Path) -> Case:
    raw = json.loads(_read_text(path))

    if not isinstance(raw, dict):
        msg = "invalid case.json (expected object): {}".format(path)
        raise TypeError(msg)

    case_id = str(raw.get("id") or "").strip()
    title = str(raw.get("title") or "").strip()
    kind = str(raw.get("kind") or "").strip()
    inputs = raw.get("inputs") or {}
    expect = raw.get("expect") or {}

    if not case_id:
        msg = "missing required field `id`: {}".format(path)
        raise ValueError(msg)
    if not title:
        msg = "missing required field `title`: {}".format(path)
        raise ValueError(msg)
    if not kind:
        msg = "missing required field `kind`: {}".format(path)
        raise ValueError(msg)
    if not isinstance(inputs, dict):
        msg = "`inputs` must be an object: {}".format(path)
        raise TypeError(msg)
    if not isinstance(expect, dict):
        msg = "`expect` must be an object: {}".format(path)
        raise TypeError(msg)

    return Case(case_id=case_id, title=title, kind=kind, inputs=inputs, expect=expect, case_dir=path.parent)


def discover_cases(cases_root: Path) -> List[Case]:
    if not cases_root.exists():
        msg = "cases root not found: {}".format(cases_root)
        raise FileNotFoundError(msg)

    case_files = sorted(cases_root.rglob("case.json"))
    cases = [_load_case(p) for p in case_files]
    cases.sort(key=lambda c: c.case_id)
    return cases


def _parse_patch(text: str) -> Tuple[FilePatch, ...]:
    file_patches: List[FilePatch] = []

    current_old: Optional[str] = None
    current_new: Optional[str] = None
    current_hunks: List[DiffHunk] = []
    current_hunk_lines: List[str] = []
    current_hunk_old_start: Optional[int] = None
    current_hunk_new_start: Optional[int] = None

    def _flush_hunk() -> None:
        nonlocal current_hunk_lines, current_hunk_old_start, current_hunk_new_start
        if current_hunk_old_start is None or current_hunk_new_start is None:
            current_hunk_lines = []
            current_hunk_old_start = None
            current_hunk_new_start = None
            return
        current_hunks.append(
            DiffHunk(
                old_start=current_hunk_old_start,
                new_start=current_hunk_new_start,
                lines=tuple(current_hunk_lines),
            )
        )
        current_hunk_lines = []
        current_hunk_old_start = None
        current_hunk_new_start = None

    def _flush_file() -> None:
        nonlocal current_old, current_new, current_hunks
        _flush_hunk()
        if current_old is None or current_new is None:
            current_hunks = []
            current_old = None
            current_new = None
            return
        file_patches.append(FilePatch(old_path=current_old, new_path=current_new, hunks=tuple(current_hunks)))
        current_hunks = []
        current_old = None
        current_new = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\n")

        file_m = _DIFF_FILE_RE.match(line)
        if file_m:
            _flush_file()
            current_old = file_m.group(1)
            current_new = file_m.group(2)
            continue

        hunk_m = _DIFF_HUNK_RE.match(line)
        if hunk_m and current_old is not None and current_new is not None:
            _flush_hunk()
            current_hunk_old_start = int(hunk_m.group(1))
            current_hunk_new_start = int(hunk_m.group(3))
            continue

        if current_hunk_old_start is not None and current_hunk_new_start is not None:
            current_hunk_lines.append(line)

    _flush_file()
    return tuple(file_patches)


def _has_gen_path(paths: Iterable[str]) -> bool:
    return any(".gen." in p for p in paths)


def _effective_existing_path(root: Path, file_patch: FilePatch) -> Optional[Path]:
    candidates = [root / file_patch.new_path, root / file_patch.old_path]
    for c in candidates:
        if c.exists() and c.is_file():
            return c
    return None


def _autogen_block_ranges(text: str) -> List[Tuple[str, int, int]]:
    # 返回的区间为闭区间(行号为 `1-based`).
    ranges: List[Tuple[str, int, int]] = []
    begin_stack: List[Tuple[str, int]] = []

    for idx, line in enumerate(text.splitlines(), start=1):
        begin_m = _AUTOGEN_BEGIN_RE.search(line)
        if begin_m:
            begin_stack.append((begin_m.group(1), idx))
            continue
        end_m = _AUTOGEN_END_RE.search(line)
        if end_m:
            block_id = end_m.group(1)
            if begin_stack and begin_stack[-1][0] == block_id:
                _, begin_idx = begin_stack.pop()
                ranges.append((block_id, begin_idx, idx))
            continue

    return ranges


def _is_in_ranges(line_no: int, ranges: Sequence[Tuple[str, int, int]]) -> Optional[str]:
    for block_id, begin, end in ranges:
        if begin <= line_no <= end:
            return block_id
    return None


def _validate_generated_file_boundary(file_patches: Sequence[FilePatch], *, allow_gen: bool) -> List[Issue]:
    if allow_gen:
        return []
    issues: List[Issue] = []
    for fp in file_patches:
        if _has_gen_path(fp.paths()):
            issues.append(
                Issue(
                    code="generated_file",
                    message="补丁涉及 `*.gen.*` 路径; 生成文件禁止手改.",
                    path=fp.new_path,
                )
            )
    return issues


def _validate_injected_block_boundary(file_patches: Sequence[FilePatch], *, root: Path) -> List[Issue]:
    issues: List[Issue] = []
    for fp in file_patches:
        base_path = _effective_existing_path(root, fp)
        if base_path is None:
            continue
        ranges = _autogen_block_ranges(_read_text(base_path))
        if not ranges:
            continue

        for hunk in fp.hunks:
            old_line = hunk.old_start
            new_line = hunk.new_start

            for line in hunk.lines:
                if not line:
                    # 防御性处理: 补丁行缺少前缀.
                    continue
                prefix = line[0]
                if prefix == " ":
                    old_line += 1
                    new_line += 1
                    continue
                if prefix == "-":
                    block_id = _is_in_ranges(old_line, ranges)
                    if block_id is not None:
                        issues.append(
                            Issue(
                                code="autogen_block",
                                message="补丁修改了注入的 `AUTOGEN` 块 `{}`; 请修改 SSOT 并重新运行 `just gen-docs`.".format(block_id),
                                path=fp.new_path,
                                line=old_line,
                            )
                        )
                    old_line += 1
                    continue
                if prefix == "+":
                    # `+` 行不会推进 `old_line`; 插入点按当前 `old_line` 处理.
                    block_id = _is_in_ranges(old_line, ranges)
                    if block_id is not None:
                        issues.append(
                            Issue(
                                code="autogen_block",
                                message="补丁向注入的 `AUTOGEN` 块 `{}` 中插入内容; 请修改 SSOT 并重新运行 `just gen-docs`.".format(
                                    block_id
                                ),
                                path=fp.new_path,
                                line=old_line,
                            )
                        )
                    new_line += 1
                    continue

    return issues


def _validate_file_assert(case: Case, *, root: Path) -> Tuple[bool, Tuple[Issue, ...]]:
    rel = str(case.inputs.get("file") or "").strip()
    must_contain = case.inputs.get("must_contain") or []

    if not rel:
        return False, (Issue(code="case_error", message="file_assert 用例缺少 `inputs.file`", path=str(case.case_dir)),)
    if not isinstance(must_contain, list) or not all(isinstance(x, str) for x in must_contain):
        return False, (Issue(code="case_error", message="file_assert `inputs.must_contain` 必须是字符串列表", path=str(case.case_dir)),)

    path = root / rel
    if not path.exists():
        return False, (Issue(code="file_missing", message="缺少必需文件", path=rel),)

    text = _read_text(path)
    violations: List[Issue] = []
    for needle in must_contain:
        if needle not in text:
            violations.append(Issue(code="missing_text", message="缺少必需片段: {}".format(needle), path=rel))
    return not violations, tuple(violations)


def _validate_diff_case(case: Case, *, root: Path) -> Tuple[bool, Tuple[Issue, ...]]:
    patch_file = str(case.inputs.get("patch_file") or "").strip()
    allow_gen = bool(case.inputs.get("allow_gen_files", False))
    if not patch_file:
        return False, (Issue(code="case_error", message="`diff` 用例缺少 `inputs.patch_file`", path=str(case.case_dir)),)

    patch_path = case.case_dir / patch_file
    if not patch_path.exists():
        return False, (Issue(code="file_missing", message="找不到补丁文件", path=str(patch_path)),)

    file_patches = _parse_patch(_read_text(patch_path))

    violations: List[Issue] = []
    violations.extend(_validate_generated_file_boundary(file_patches, allow_gen=allow_gen))
    violations.extend(_validate_injected_block_boundary(file_patches, root=root))

    observed_ok = not violations
    expected_ok = bool(case.expect.get("ok", True))
    expected_codes_raw = case.expect.get("issue_codes")
    expected_codes: List[str] = []
    if isinstance(expected_codes_raw, list) and all(isinstance(x, str) for x in expected_codes_raw):
        expected_codes = expected_codes_raw

    mismatch: List[Issue] = []
    if observed_ok != expected_ok:
        mismatch.append(
            Issue(
                code="unexpected_pass" if observed_ok else "unexpected_failure",
                message="期望 ok={}，实际 ok={}.".format(expected_ok, observed_ok),
            )
        )

    if expected_codes:
        actual_codes = {i.code for i in violations}
        missing = [c for c in expected_codes if c not in actual_codes]
        if missing:
            mismatch.append(Issue(code="missing_expected_issue", message="缺少期望的违规 `code`: {}".format(", ".join(missing))))

    return not mismatch, tuple(violations + mismatch)


def run_cases(cases: Sequence[Case], *, root: Path) -> List[CaseResult]:
    results: List[CaseResult] = []
    for case in cases:
        expected_ok = bool(case.expect.get("ok", True))

        if case.kind == "diff":
            case_ok, issues = _validate_diff_case(case, root=root)
            violations = tuple(i for i in issues if i.code in ("generated_file", "autogen_block"))
            mismatch = tuple(i for i in issues if i.code not in ("generated_file", "autogen_block"))
            observed_ok = not violations
            results.append(
                CaseResult(
                    case_id=case.case_id,
                    title=case.title,
                    kind=case.kind,
                    ok=case_ok,
                    expected_ok=expected_ok,
                    observed_ok=observed_ok,
                    violations=violations,
                    issues=mismatch,
                )
            )
            continue
        elif case.kind == "file_assert":
            observed_ok, violations = _validate_file_assert(case, root=root)
            mismatch: List[Issue] = []
            if observed_ok != expected_ok:
                mismatch.append(
                    Issue(
                        code="unexpected_pass" if observed_ok else "unexpected_failure",
                        message="期望 ok={}，实际 ok={}.".format(expected_ok, observed_ok),
                    )
                )
            case_ok = not mismatch
            results.append(
                CaseResult(
                    case_id=case.case_id,
                    title=case.title,
                    kind=case.kind,
                    ok=case_ok,
                    expected_ok=expected_ok,
                    observed_ok=observed_ok,
                    violations=violations,
                    issues=tuple(mismatch),
                )
            )
            continue
        else:
            results.append(
                CaseResult(
                    case_id=case.case_id,
                    title=case.title,
                    kind=case.kind,
                    ok=False,
                    expected_ok=expected_ok,
                    observed_ok=False,
                    violations=(),
                    issues=(Issue(code="case_error", message="未知的用例类型: {}".format(case.kind), path=str(case.case_dir)),),
                )
            )

    results.sort(key=lambda r: r.case_id)
    return results


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    lines = [json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _write_failures_md(path: Path, results: Sequence[CaseResult]) -> None:
    failed = [r for r in results if not r.ok]
    if not failed:
        path.write_text("# prompt-eval failures\n\n(no failures)\n", encoding="utf-8")
        return

    lines: List[str] = ["# prompt-eval failures", ""]
    for r in failed:
        lines.append("## {}".format(r.case_id))
        lines.append("")
        lines.append(r.title)
        lines.append("")
        for issue in [*r.issues, *r.violations]:
            where = ""
            if issue.path is not None:
                where = issue.path
                if issue.line is not None:
                    where = "{}:{}".format(where, issue.line)
                where = " ({})".format(where)
            lines.append("- `[{}]` {}{}".format(issue.code, issue.message, where))
        lines.append("")

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _print_summary(results: Sequence[CaseResult]) -> None:
    total = len(results)
    passed = sum(1 for r in results if r.ok)
    failed = total - passed

    for r in results:
        tag = "PASS" if r.ok else "FAIL"
        print("[{}] {} - {}".format(tag, r.case_id, r.title))
        if not r.ok:
            for issue in [*r.issues, *r.violations]:
                where = ""
                if issue.path is not None:
                    where = issue.path
                    if issue.line is not None:
                        where = "{}:{}".format(where, issue.line)
                    where = " ({})".format(where)
                print("  - [{}] {}{}".format(issue.code, issue.message, where))

    print("")
    print("用例统计: 总计={} 通过={} 失败={}".format(total, passed, failed))


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog=_RUNNER_NAME)
    parser.add_argument(
        "--cases-root", default="openspec/prompt-eval/cases", help="Cases root directory (default: openspec/prompt-eval/cases)"
    )
    parser.add_argument("--output-dir", default=".tmp/artifacts/prompt-eval", help="Output directory (default: .tmp/artifacts/prompt-eval)")
    parser.add_argument("--check", action="store_true", help="CI mode: deterministic core only")
    parser.add_argument("--llm", action="store_true", help="Enable optional LLM suite (requires extra tooling; not enabled by default)")
    args = parser.parse_args(list(argv) if argv is not None else None)

    root = _repo_root()
    cases_root = root / args.cases_root
    out_dir = root / args.output_dir

    if args.llm:
        print("[错误] LLM 套件尚未配置. 请先运行确定性 `core`: `just prompt-eval`")
        return 2

    cases = discover_cases(cases_root)
    results = run_cases(cases, root=root)

    # 总是写出产物(CI 会上传 `.tmp/artifacts/`).
    _safe_rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    head = _git_head(root)
    total = len(results)
    passed = sum(1 for r in results if r.ok)
    failed = total - passed
    ok = failed == 0

    summary: Dict[str, Any] = {
        "runner": {"name": _RUNNER_NAME, "version": _RUNNER_VERSION},
        "git": {"head": head},
        "cases": {"total": total, "passed": passed, "failed": failed},
        "ok": ok,
        "mode": "check" if args.check else "run",
    }

    _write_json(out_dir / "summary.json", summary)
    _write_jsonl(out_dir / "cases.jsonl", [r.as_dict() for r in results])
    _write_failures_md(out_dir / "failures.md", results)

    _print_summary(results)

    if not ok:
        print("[错误] `prompt-eval` 执行失败; 详见 {}".format(out_dir / "failures.md"), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
