#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""
扫描 `.tmp/known-outer-paths-using-this-package.txt` 中列出的下游目录,检查其 YAML DSL 配置是否符合当前仓库语义.

隐私约束:
- 不在 `stdout`/`stderr` 中输出下游路径明细(包含该列表文件中的条目内容).
- 仅输出统计与行号; 详细诊断写入 `.tmp/output/downstream-yaml-dsl-scan/line-<N>.json`.
- 日志文件中也不写入下游根目录绝对路径; 仅写入 YAML 文件的 `repo-relative` 路径.

注意:
- 这是“盘点/调研”工具: 不会修改下游 `repo` 的任何文件.
- 依赖本仓库环境提供 `uv` 与 `scalim-cli`(通过 `uv run scalim-cli ...` 调用).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


DEFAULT_LIST_REL = Path(".tmp") / "known-outer-paths-using-this-package.txt"
DEFAULT_OUTPUT_DIR_REL = Path(".tmp") / "output" / "downstream-yaml-dsl-scan"

WORKFLOW_SCHEMA_REL = Path("src") / "scalim" / "dsl" / "by_yaml" / "schema" / "workflow.gen.json"

_CANDIDATE_TOPLEVEL_RE = re.compile(r"(?m)^(main_source|sources|fields|relations|outputs|output|workflow):")
_WORKFLOW_RE = re.compile(r"(?m)^workflow:")

_PATTERNS: Dict[str, re.Pattern[str]] = {
    "legacy_runtime_placeholder": re.compile(r"\$runtime\."),
    "top_level_output": re.compile(r"(?m)^output:"),
    "legacy_bind": re.compile(r"(?m)^(bind|to_bind):"),
    "legacy_field_kw": re.compile(r"(?m)^\s*field\s*:"),
}


@dataclass(frozen=True)
class _Entry:
    line_no: int
    raw: str


@dataclass
class _FileResult:
    rel_path: str
    kind: str  # `demand`|`workflow`(需求/工作流)
    ok: bool
    errors: int
    warnings: int
    issues: List[Dict[str, Any]]


@dataclass
class _DownstreamResult:
    line_no: int
    ok: bool
    entry_kind: str  # `scanned`|`missing`|`not_dir`|`error`
    candidate_yaml_files: int
    demand_files: int
    workflow_files: int
    validate_ok: int
    validate_fail: int
    pattern_hits: Dict[str, int]
    top_messages: List[str]
    files: List[_FileResult]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _run(cmd: Sequence[str], *, cwd: Optional[Path] = None, timeout_s: int = 120) -> Tuple[int, str, str]:
    p = subprocess.run(
        list(cmd),
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout_s,
    )
    return p.returncode, p.stdout, p.stderr


def _load_entries(list_path: Path) -> List[_Entry]:
    lines = list_path.read_text(encoding="utf-8").splitlines()
    out: List[_Entry] = []
    for i, raw in enumerate(lines, 1):
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        out.append(_Entry(line_no=i, raw=s))
    return out


def _resolve_entry_path(value: str, *, repo_root: Path) -> Path:
    expanded = os.path.expanduser(value.strip())
    p = Path(expanded)
    if not p.is_absolute():
        p = (repo_root / p).resolve()
    else:
        p = p.resolve()
    return p


def _dedup_keep_order(items: Iterable[str], *, limit: int) -> List[str]:
    out: List[str] = []
    seen = set()
    for x in items:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
        if len(out) >= limit:
            break
    return out


def _extract_json_payload(stdout: str) -> Optional[dict]:
    s = stdout.strip()
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        pass
    # 兜底: 尝试从 `stdout` 末尾提取最后一个 `JSON` 对象
    last = s.rfind("{")
    if last == -1:
        return None
    try:
        return json.loads(s[last:])
    except Exception:
        return None


def _payload_to_issues(payload: dict) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for k in ("errors", "warnings"):
        for it in payload.get(k, []) or []:
            # 重要: 不要向外透出文件系统路径(例如 `yaml_path`/`location`)
            out.append(
                {
                    "level": "error" if k == "errors" else "warning",
                    "path": str(it.get("path", "") or ""),
                    "message": str(it.get("message", "") or ""),
                    "suggestions": list(it.get("suggestions", []) or []),
                }
            )
    return out


def _issues_to_messages(issues: List[Dict[str, Any]]) -> List[str]:
    msgs: List[str] = []
    for it in issues:
        path = str(it.get("path", "") or "").strip()
        msg = str(it.get("message", "") or "").strip()
        if path and msg:
            msgs.append(f"{path}: {msg}")
        elif msg:
            msgs.append(msg)
        elif path:
            msgs.append(path)
    return msgs


def _is_workflow_yaml(text: str) -> bool:
    return bool(_WORKFLOW_RE.search(text))


def _candidate_yaml_files_by_rg(root: Path) -> List[Path]:
    # 注意: `rg` 输出里包含文件路径; 我们不会把它们打印到 `stdout`.
    cmd = ["rg", "-l", "-S", "--glob=*.yaml", "--glob=*.yml", _CANDIDATE_TOPLEVEL_RE.pattern, "."]
    code, out, _err = _run(cmd, cwd=root, timeout_s=90)
    if code not in (0, 1):  # `1` 表示无匹配
        return []
    files = [root / p for p in out.splitlines() if p.strip()]
    return files


def _candidate_yaml_files_fallback(root: Path) -> List[Path]:
    skip = {".git", ".venv", "venv", "__pycache__", "node_modules", "dist", "build", ".mypy_cache", ".ruff_cache"}
    out: List[Path] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix not in (".yaml", ".yml"):
            continue
        parts = set(p.parts)
        if parts & skip:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if _CANDIDATE_TOPLEVEL_RE.search(text):
            out.append(p)
    return out


def _candidate_yaml_files(root: Path) -> List[Path]:
    if shutil_which("rg") is not None:
        files = _candidate_yaml_files_by_rg(root)
        if files:
            return files
    return _candidate_yaml_files_fallback(root)


def shutil_which(cmd: str) -> Optional[str]:
    # 本地小工具: 仅为 `which` 功能,避免引入 `shutil`
    path = os.environ.get("PATH", "")
    for d in path.split(os.pathsep):
        p = Path(d) / cmd
        if p.exists() and os.access(str(p), os.X_OK):
            return str(p)
    return None


def _count_pattern_hits(files: List[Path]) -> Dict[str, int]:
    hits = {k: 0 for k in _PATTERNS}
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for k, rx in _PATTERNS.items():
            hits[k] += len(rx.findall(text))
    return hits


def _validate_yaml_file(
    yaml_path: Path,
    *,
    repo_root: Path,
    cli_prefix: Sequence[str],
    workflow_schema: Path,
    timeout_s: int,
) -> _FileResult:
    rel_path = yaml_path.as_posix()
    try:
        text = yaml_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return _FileResult(
            rel_path=rel_path,
            kind="unknown",
            ok=False,
            errors=1,
            warnings=0,
            issues=[{"level": "error", "path": "", "message": "读取 `YAML` 失败"}],
        )

    if _is_workflow_yaml(text):
        kind = "workflow"
        cmd = [
            *cli_prefix,
            "yaml-dsl",
            "schema",
            "validate",
            "--strict",
            "--json",
            "--schema",
            str(workflow_schema),
            str(yaml_path),
        ]
    else:
        kind = "demand"
        cmd = [
            *cli_prefix,
            "yaml-dsl",
            "validate",
            "--strict",
            "--json",
            str(yaml_path),
        ]

    code, out, err = _run(cmd, cwd=repo_root, timeout_s=timeout_s)
    payload = _extract_json_payload(out)
    if payload is None:
        # 兜底错误: 保持错误信息不包含路径
        _ = code
        _ = err
        return _FileResult(
            rel_path=rel_path,
            kind=kind,
            ok=False,
            errors=1,
            warnings=0,
            issues=[{"level": "error", "path": "", "message": "校验输出未包含 `JSON` 载荷"}],
        )

    ok = bool(payload.get("ok", False))
    errors = len(payload.get("errors", []) or [])
    warnings = len(payload.get("warnings", []) or [])
    issues = _payload_to_issues(payload)
    _ = code
    _ = err
    return _FileResult(rel_path=rel_path, kind=kind, ok=ok, errors=errors, warnings=warnings, issues=issues)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="扫描外部路径清单中的下游 YAML DSL 配置(不泄露路径明细).")
    p.add_argument("--file", default=str(DEFAULT_LIST_REL), help="列表文件路径(默认: .tmp/known-outer-paths-using-this-package.txt)")
    p.add_argument(
        "--cli",
        default="uv run scalim-cli",
        help="用于执行 scalim-cli 的命令前缀(默认: 'uv run scalim-cli').",
    )
    p.add_argument("--timeout-s", type=int, default=120, help="单个 YAML 校验超时(秒).")
    p.add_argument("--max-files-per-downstream", type=int, default=200, help="每个下游最多校验的候选 YAML 文件数(防止误扫巨大仓库).")
    p.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR_REL), help="输出目录(默认: .tmp/output/downstream-yaml-dsl-scan).")
    p.add_argument("--fail-on-pattern-hits", action="store_true", help="若命中典型 legacy pattern(如 $runtime.) 也视为失败.")
    return p.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    repo_root = _repo_root()

    list_path = Path(args.file)
    if not list_path.is_absolute():
        list_path = (repo_root / list_path).resolve()
    if not list_path.exists():
        print("未找到列表文件: {}".format(list_path), file=sys.stderr)
        return 2

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = (repo_root / output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    workflow_schema = (repo_root / WORKFLOW_SCHEMA_REL).resolve()
    if not workflow_schema.exists():
        print("未找到 `workflow` 的 `schema` 文件: {}".format(workflow_schema), file=sys.stderr)
        return 2

    cli_prefix = shlex.split(str(args.cli))
    if not cli_prefix:
        print("参数 `--cli` 不能为空", file=sys.stderr)
        return 2

    entries = _load_entries(list_path)
    results: List[_DownstreamResult] = []

    for e in entries:
        downstream_root = _resolve_entry_path(e.raw, repo_root=repo_root)
        if not downstream_root.exists():
            results.append(
                _DownstreamResult(
                    line_no=e.line_no,
                    ok=False,
                    entry_kind="missing",
                    candidate_yaml_files=0,
                    demand_files=0,
                    workflow_files=0,
                    validate_ok=0,
                    validate_fail=0,
                    pattern_hits={k: 0 for k in _PATTERNS},
                    top_messages=["路径不存在"],
                    files=[],
                )
            )
            continue
        if not downstream_root.is_dir():
            results.append(
                _DownstreamResult(
                    line_no=e.line_no,
                    ok=False,
                    entry_kind="not_dir",
                    candidate_yaml_files=0,
                    demand_files=0,
                    workflow_files=0,
                    validate_ok=0,
                    validate_fail=0,
                    pattern_hits={k: 0 for k in _PATTERNS},
                    top_messages=["路径不是目录"],
                    files=[],
                )
            )
            continue

        candidate_files = _candidate_yaml_files(downstream_root)
        if len(candidate_files) > int(args.max_files_per_downstream):
            candidate_files = candidate_files[: int(args.max_files_per_downstream)]

        pattern_hits = _count_pattern_hits(candidate_files)
        file_results: List[_FileResult] = []

        demand_files = 0
        workflow_files = 0
        ok_count = 0
        fail_count = 0
        msgs: List[str] = []

        for f in candidate_files:
            rel = f.relative_to(downstream_root).as_posix()
            r = _validate_yaml_file(
                f,
                repo_root=repo_root,
                cli_prefix=cli_prefix,
                workflow_schema=workflow_schema,
                timeout_s=int(args.timeout_s),
            )
            r.rel_path = rel  # 仅保存“下游根目录相对路径”(不含绝对路径)
            file_results.append(r)

            if r.kind == "workflow":
                workflow_files += 1
            elif r.kind == "demand":
                demand_files += 1
            if r.ok:
                ok_count += 1
            else:
                fail_count += 1
                msgs.extend(_issues_to_messages(r.issues))

        # 计算整体 OK/FAIL
        ok = fail_count == 0
        if args.fail_on_pattern_hits:
            ok = ok and all(v == 0 for v in pattern_hits.values())

        top_msgs = _dedup_keep_order([m for m in msgs if m], limit=10)

        res = _DownstreamResult(
            line_no=e.line_no,
            ok=ok,
            entry_kind="scanned",
            candidate_yaml_files=len(candidate_files),
            demand_files=demand_files,
            workflow_files=workflow_files,
            validate_ok=ok_count,
            validate_fail=fail_count,
            pattern_hits=pattern_hits,
            top_messages=top_msgs,
            files=file_results,
        )
        results.append(res)

        # 按行号写出 `JSON` 结果(不含下游绝对路径)
        out_path = output_dir / "line-{}.json".format(e.line_no)
        out_payload = {
            "line_no": res.line_no,
            "ok": res.ok,
            "entry_kind": res.entry_kind,
            "candidate_yaml_files": res.candidate_yaml_files,
            "demand_files": res.demand_files,
            "workflow_files": res.workflow_files,
            "validate_ok": res.validate_ok,
            "validate_fail": res.validate_fail,
            "pattern_hits": res.pattern_hits,
            "top_messages": res.top_messages,
            "files": [
                {
                    "rel_path": fr.rel_path,
                    "kind": fr.kind,
                    "ok": fr.ok,
                    "errors": fr.errors,
                    "warnings": fr.warnings,
                    "issues": fr.issues,
                }
                for fr in res.files
            ],
        }
        out_path.write_text(json.dumps(out_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # 打印脱敏后的汇总(不含路径明细)
    failures = [r for r in results if not r.ok]
    print("下游条目扫描: {}".format(len(results)))
    print("- 通过: {}".format(len(results) - len(failures)))
    print("- 失败: {}".format(len(failures)))

    for r in results:
        status = "通过" if r.ok else "失败"
        print(
            "行 {}: {} | YAML 文件={} (需求={}, 工作流={}) | 校验 通过/失败={}/{} | 命中: `legacy_$runtime`={} `output`={} `bind`={} `field_kw`={}".format(
                r.line_no,
                status,
                r.candidate_yaml_files,
                r.demand_files,
                r.workflow_files,
                r.validate_ok,
                r.validate_fail,
                r.pattern_hits["legacy_runtime_placeholder"],
                r.pattern_hits["top_level_output"],
                r.pattern_hits["legacy_bind"],
                r.pattern_hits["legacy_field_kw"],
            )
        )
        if not r.ok and r.top_messages:
            for m in r.top_messages[:5]:
                print("  - {}".format(m))
            print("  - 诊断: {}".format((Path(args.output_dir) / "line-{}.json".format(r.line_no)).as_posix()))

    return 1 if failures else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
