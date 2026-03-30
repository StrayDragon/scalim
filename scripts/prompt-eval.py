# ruff: noqa: T201
from __future__ import annotations

import argparse
import io
import json
import shutil
import subprocess
import sys
import tarfile
from os import environ
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from prompt_eval.diff_validation import (
    Issue,
    parse_patch,
    read_text,
    validate_generated_file_boundary,
    validate_injected_block_boundary,
)

_RUNNER_NAME = "prompt-eval"
_RUNNER_VERSION = "0.1.0"
_SKILL_DOC_ENV = "SCALIM_PROMPT_EVAL_SKILL_DOC_PATH"
_AGENT_WORKDIR_SCHEMA_HEADER = "__SCALIM_AGENT_WORKDIR_SCHEMA_HEADER__"
_AGENT_WORKDIR_DERIVED_FIELDS = "__SCALIM_AGENT_WORKDIR_DERIVED_FIELDS__"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


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


def _load_case(path: Path) -> Case:
    raw = json.loads(read_text(path))

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

    text = read_text(path)
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

    file_patches = parse_patch(read_text(patch_path))
    if not file_patches:
        return (
            False,
            (Issue(code="patch_parse", message="无法解析补丁(缺少 `diff --git a/... b/...` 头).", path=str(patch_path)),),
        )

    violations: List[Issue] = []
    violations.extend(validate_generated_file_boundary(file_patches, allow_gen=allow_gen))
    violations.extend(validate_injected_block_boundary(file_patches, root=root))

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


def _write_promptfoo_failures_md(path: Path, payload: Dict[str, Any]) -> None:
    results = (payload.get("results") or {}).get("results") or []
    if not isinstance(results, list) or not results:
        path.write_text("# prompt-eval-llm failures\n\n(no failures)\n", encoding="utf-8")
        return

    failed = [r for r in results if isinstance(r, dict) and not r.get("success", False)]
    if not failed:
        path.write_text("# prompt-eval-llm failures\n\n(no failures)\n", encoding="utf-8")
        return

    def _s(v: Any, *, max_len: int = 900) -> str:
        text = str(v or "")
        if len(text) > max_len:
            return text[: max_len - 3] + "..."
        return text

    lines: List[str] = ["# prompt-eval-llm failures", ""]
    for r in failed:
        prompt_label = ((r.get("prompt") or {}) if isinstance(r.get("prompt"), dict) else {}).get("label") or ""
        provider_id = ((r.get("provider") or {}) if isinstance(r.get("provider"), dict) else {}).get("id") or ""
        test_desc = ((r.get("testCase") or {}) if isinstance(r.get("testCase"), dict) else {}).get("description") or ""
        error = r.get("error") or ""
        grading = r.get("gradingResult") or {}

        reason = ""
        if error:
            reason = error
        elif isinstance(grading, dict):
            reason = grading.get("reason") or ""

        lines.append("## {}".format(_s(test_desc, max_len=200)))
        lines.append("")
        if prompt_label:
            lines.append("- prompt: {}".format(_s(prompt_label, max_len=200)))
        if provider_id:
            lines.append("- provider: {}".format(_s(provider_id, max_len=200)))
        if reason:
            lines.append("- reason: {}".format(_s(reason)))
        else:
            lines.append("- reason: (no reason)")
        lines.append("")

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _promptfoo_version() -> Optional[str]:
    try:
        out = subprocess.check_output(["promptfoo", "--version"])
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    value = out.decode("utf-8", errors="ignore").strip()
    return value or None


def _file_url(path: Path) -> str:
    return "file://{}".format(path.as_posix())


def _rel_or_abs(path: Path, root: Path) -> str:
    if path == root or root in path.parents:
        return str(path.relative_to(root))
    return str(path)


def _extract_git_archive(*, root: Path, ref: str, rel_path: str, dest_dir: Path) -> None:
    try:
        blob = subprocess.check_output(["git", "archive", ref, rel_path], cwd=str(root))
    except subprocess.CalledProcessError as e:
        msg = "git archive failed for ref={} path={}: {}".format(ref, rel_path, e)
        raise RuntimeError(msg)

    dest_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:*") as tf:
        tf.extractall(path=str(dest_dir))


def _materialize_skill_snapshot_candidate(*, root: Path, dest_dir: Path) -> Path:
    src = root / "artifacts/skills/scalim-yaml-dsl"
    if not src.exists() or not src.is_dir():
        msg = "candidate skill directory not found: {}".format(src)
        raise FileNotFoundError(msg)

    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    out_dir = dest_dir / "scalim-yaml-dsl"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(str(src), str(out_dir))
    skill_md = out_dir / "SKILL.md"
    if not skill_md.exists():
        msg = "candidate SKILL.md not found after snapshot: {}".format(skill_md)
        raise FileNotFoundError(msg)
    return skill_md


def _materialize_skill_snapshot_baseline(*, root: Path, ref: str, dest_dir: Path) -> Path:
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    _extract_git_archive(root=root, ref=ref, rel_path="artifacts/skills/scalim-yaml-dsl", dest_dir=dest_dir)

    extracted = dest_dir / "artifacts/skills/scalim-yaml-dsl"
    if not extracted.exists():
        msg = "baseline skill directory not found in git archive output: {} (ref={})".format(extracted, ref)
        raise FileNotFoundError(msg)

    out_dir = dest_dir / "scalim-yaml-dsl"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.move(str(extracted), str(out_dir))

    artifacts_dir = dest_dir / "artifacts"
    if artifacts_dir.exists():
        shutil.rmtree(artifacts_dir)

    skill_md = out_dir / "SKILL.md"
    if not skill_md.exists():
        msg = "baseline SKILL.md not found after snapshot: {} (ref={})".format(skill_md, ref)
        raise FileNotFoundError(msg)
    return skill_md


def _render_promptfoo_config_for_skill(*, ssot_path: Path, dest_path: Path, skill_md_path: Path) -> None:
    ssot_text = read_text(ssot_path)
    needle = "file://../../../artifacts/skills/scalim-yaml-dsl/SKILL.md"
    if needle not in ssot_text:
        msg = "promptfoo SSOT config missing expected prefix reference: {}".format(needle)
        raise RuntimeError(msg)
    rendered = ssot_text.replace(needle, _file_url(skill_md_path))
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_text(rendered, encoding="utf-8")


def _render_promptfoo_config_with_replacements(*, ssot_path: Path, dest_path: Path, replacements: Dict[str, str]) -> None:
    ssot_text = read_text(ssot_path)
    rendered = ssot_text
    for needle, value in replacements.items():
        if needle not in rendered:
            msg = "promptfoo SSOT config missing placeholder: {}".format(needle)
            raise RuntimeError(msg)
        rendered = rendered.replace(needle, value)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_text(rendered, encoding="utf-8")


def _setup_agent_workspace(*, root: Path, workspace_dir: Path, skill_dir: Path, scenario: str) -> None:
    fixture_dir = root / "agentdev/prompt-eval/fixtures/agent_stub_project"
    if not fixture_dir.exists():
        msg = "agent fixture missing: {}".format(fixture_dir)
        raise FileNotFoundError(msg)
    if workspace_dir.exists():
        shutil.rmtree(workspace_dir)
    workspace_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(str(fixture_dir), str(workspace_dir))

    # 预先创建本地 `uv` 虚拟环境并生成虚拟环境内的入口脚本,确保
    # `uv run scalim-cli ...` 会解析到工作区内的 `stub`(而不是任何全局安装的版本)。
    try:
        uv_env = dict(environ)
        active_venv = uv_env.pop("VIRTUAL_ENV", None)
        if active_venv:
            venv_bin = str(Path(active_venv) / "bin")
            path_raw = uv_env.get("PATH") or ""
            uv_env["PATH"] = ":".join(p for p in path_raw.split(":") if p and p != venv_bin)

        subprocess.check_call(["uv", "-q", "venv"], cwd=str(workspace_dir), env=uv_env)

        # 注意:这里不要解析符号链接。`uv venv` 可能把虚拟环境的 `python` 符号链接到 `uv` 管理的解释器;
        # 对我们来说,只需要虚拟环境内的路径,用于生成脚本的 `shebang` 行。
        workspace_python = workspace_dir / ".venv" / "bin" / "python"
        if not workspace_python.exists():
            raise RuntimeError("智能体工作区的 `python` 不存在: {}".format(workspace_python))

        venv_bin_dir = workspace_dir / ".venv" / "bin"
        src_dir = workspace_dir / "src"
        if not src_dir.exists():
            raise RuntimeError("智能体工作区的样例源码目录不存在: {}".format(src_dir))

        # 避免在这里执行 `uv pip install -e .`: 它会引入构建依赖(例如 `setuptools`),
        # 并可能需要访问 `PyPI` 网络,导致 `prompt-eval` 的 `dry-run` 不稳定。
        # 这里改为生成虚拟环境内的命令行脚本,从 `./src` 直接导入 `fixture` 代码。
        script = "\n".join(
            [
                "#!{}".format(workspace_python),
                "# -*- coding: utf-8 -*-",
                "import sys",
                "from pathlib import Path",
                "",
                "",
                "def _main() -> int:",
                "    root = Path(__file__).resolve().parents[2]",
                '    sys.path.insert(0, str(root / "src"))',
                "    from scalim_agent_fixture.cli import main",
                "    return int(main())",
                "",
                "",
                'if __name__ == "__main__":',
                "    raise SystemExit(_main())",
                "",
            ]
        )

        # `fixture` 只注册 `scalim-fixture-cli`。这里额外创建一个工作区内的 `scalim-cli` 垫片脚本,
        # 让执行器仍可按技能文档的模板命令原样执行。
        for entrypoint in ("scalim-fixture-cli", "scalim-cli"):
            path = venv_bin_dir / entrypoint
            path.write_text(script, encoding="utf-8")
            path.chmod(0o755)
    except FileNotFoundError:
        raise RuntimeError("缺少必需依赖: `uv`(用于智能体工作区初始化)。")
    except subprocess.CalledProcessError as e:
        raise RuntimeError("初始化智能体工作区的 `uv` 虚拟环境失败: {}".format(e))

    schema_dir = workspace_dir / "schema"
    schema_dir.mkdir(parents=True, exist_ok=True)
    schema_path = (schema_dir / "demand.gen.json").resolve()
    schema_path.write_text('{"type":"object"}\n', encoding="utf-8")

    reports_dir = workspace_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    if scenario == "schema_header":
        yaml_path = reports_dir / "schema_header_bad.gen.yaml"
        yaml_path.write_text(
            "\n".join(
                [
                    "# yaml-language-server: $schema=/wrong/path/demand.gen.json",
                    "",
                    "main_source:",
                    "  fields:",
                    "    raw_a:",
                    "      data_key: raw_a",
                    "fields:",
                    "  derived_x:",
                    "    compute: raw_a",
                    "",
                ]
            ),
            encoding="utf-8",
        )
    elif scenario == "derived_fields":
        yaml_path = reports_dir / "derived_fields_bad.gen.yaml"
        yaml_path.write_text(
            "\n".join(
                [
                    "# yaml-language-server: $schema={}".format(schema_path),
                    "",
                    "main_source:",
                    "  fields:",
                    "    raw_a:",
                    "      data_key: raw_a",
                    "    derived_total:",
                    "      compute: raw_a",
                    "fields: {}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
    else:
        msg = "unknown agent scenario: {}".format(scenario)
        raise ValueError(msg)

    skill_dest = workspace_dir / "artifacts/skills/scalim-yaml-dsl"
    skill_dest.parent.mkdir(parents=True, exist_ok=True)
    if skill_dest.exists():
        shutil.rmtree(skill_dest)
    shutil.copytree(str(skill_dir), str(skill_dest))


def _setup_agent_workspaces(*, root: Path, workspaces_root: Path, skill_dir: Path) -> Dict[str, str]:
    workspaces_root.mkdir(parents=True, exist_ok=True)
    replacements: Dict[str, str] = {}

    schema_ws = workspaces_root / "schema_header_fix"
    _setup_agent_workspace(root=root, workspace_dir=schema_ws, skill_dir=skill_dir, scenario="schema_header")
    replacements[_AGENT_WORKDIR_SCHEMA_HEADER] = str(schema_ws)

    derived_ws = workspaces_root / "derived_fields_upgrade"
    _setup_agent_workspace(root=root, workspace_dir=derived_ws, skill_dir=skill_dir, scenario="derived_fields")
    replacements[_AGENT_WORKDIR_DERIVED_FIELDS] = str(derived_ws)

    return replacements


def _promptfoo_common_cmd(*, config_path: Path, out_path: Path) -> List[str]:
    cmd = [
        "promptfoo",
        "eval",
        "-c",
        str(config_path),
        "-o",
        str(out_path),
        "--no-share",
        "--no-progress-bar",
        "--no-table",
    ]

    max_concurrency = environ.get("PROMPT_EVAL_LLM_MAX_CONCURRENCY")
    if max_concurrency:
        cmd.extend(["-j", max_concurrency])

    filter_first_n = environ.get("PROMPT_EVAL_LLM_FILTER_FIRST_N")
    if filter_first_n:
        cmd.extend(["-n", filter_first_n])

    filter_pattern = environ.get("PROMPT_EVAL_LLM_FILTER_PATTERN")
    if filter_pattern:
        cmd.extend(["--filter-pattern", filter_pattern])

    filter_prompts = environ.get("PROMPT_EVAL_LLM_FILTER_PROMPTS")
    if filter_prompts:
        cmd.extend(["--filter-prompts", filter_prompts])

    if environ.get("PROMPT_EVAL_LLM_NO_CACHE") == "1":
        cmd.append("--no-cache")

    return cmd


def _run_promptfoo_once(
    *,
    root: Path,
    output_dir: Path,
    config_path: Path,
    actual_version: str,
    pinned_version: Optional[str],
    git_head: Optional[str],
    check: bool,
    variant: Optional[str],
    baseline_ref: Optional[str],
    skill_md_path: Optional[Path],
) -> Tuple[int, Dict[str, Any]]:
    work_dir = output_dir / "promptfoo-workdir"
    promptfoo_out = output_dir / "promptfoo-output.json"
    summary_path = output_dir / "summary.json"
    failures_path = output_dir / "failures.md"

    # 保持 `work_dir` 持久化,复用 `promptfoo` 的缓存(减少重复运行的 `token`/时间开销)。
    output_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    for artifact in (summary_path, promptfoo_out, failures_path):
        if artifact.exists():
            artifact.unlink()

    # 先校验配置,再开始消耗 `token`。
    try:
        subprocess.check_call(["promptfoo", "validate", "config", "-c", str(config_path)], cwd=str(work_dir))
    except subprocess.CalledProcessError:
        print("[错误] `promptfoo` 配置校验失败: {}".format(config_path), file=sys.stderr)
        return 2, {}

    dry_run = environ.get("PROMPT_EVAL_LLM_DRY_RUN") == "1"
    if dry_run:
        summary: Dict[str, Any] = {
            "runner": {"name": _RUNNER_NAME, "version": _RUNNER_VERSION},
            "mode": "check" if check else "run",
            "git": {"head": git_head},
            "promptfoo": {
                "version": actual_version,
                "pinned": pinned_version,
                "config": _rel_or_abs(config_path, root),
                "output": _rel_or_abs(promptfoo_out, root),
            },
            "ok": True,
            "dry_run": True,
        }
        if variant is not None:
            summary["variant"] = variant
        if baseline_ref is not None:
            summary["baseline_ref"] = baseline_ref
        if skill_md_path is not None:
            summary["skill_doc"] = _rel_or_abs(skill_md_path, root)
        _write_json(summary_path, summary)
        return 0, summary

    cmd = _promptfoo_common_cmd(config_path=config_path, out_path=promptfoo_out)

    env = dict(environ)
    active_venv = env.pop("VIRTUAL_ENV", None)
    if active_venv:
        venv_bin = str(Path(active_venv) / "bin")
        path_raw = env.get("PATH") or ""
        env["PATH"] = ":".join(p for p in path_raw.split(":") if p and p != venv_bin)
    env.setdefault("PROMPTFOO_PYTHON", sys.executable)
    env.setdefault("PROMPTFOO_DISABLE_SHARING", "1")
    env.setdefault("PROMPTFOO_DISABLE_SHARE_EMAIL_REQUEST", "1")
    if skill_md_path is not None:
        env[_SKILL_DOC_ENV] = str(skill_md_path)

    rc = subprocess.call(cmd, cwd=str(work_dir), env=env)

    summary = {
        "runner": {"name": _RUNNER_NAME, "version": _RUNNER_VERSION},
        "mode": "check" if check else "run",
        "git": {"head": git_head},
        "promptfoo": {
            "version": actual_version,
            "pinned": pinned_version,
            "config": _rel_or_abs(config_path, root),
            "output": _rel_or_abs(promptfoo_out, root),
        },
        "ok": rc == 0,
    }
    if variant is not None:
        summary["variant"] = variant
    if baseline_ref is not None:
        summary["baseline_ref"] = baseline_ref
    if skill_md_path is not None:
        summary["skill_doc"] = _rel_or_abs(skill_md_path, root)

    if promptfoo_out.exists():
        try:
            payload = json.loads(read_text(promptfoo_out))
        except Exception as e:
            summary["parse_error"] = str(e)
        else:
            stats = (payload.get("results") or {}).get("stats") or {}
            summary["stats"] = stats
            summary["evalId"] = payload.get("evalId")
            _write_promptfoo_failures_md(failures_path, payload)

    _write_json(summary_path, summary)
    return rc, summary


def _load_promptfoo_rows(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = (payload.get("results") or {}).get("results") or []
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict)]


def _row_key(row: Dict[str, Any]) -> str:
    prompt = row.get("prompt") or {}
    provider = row.get("provider") or {}
    test_case = row.get("testCase") or {}
    prompt_id = ""
    prompt_label = ""
    provider_id = ""
    test_desc = ""
    if isinstance(prompt, dict):
        prompt_id = str(prompt.get("id") or "")
        prompt_label = str(prompt.get("label") or "")
    if isinstance(provider, dict):
        provider_id = str(provider.get("id") or "")
    if isinstance(test_case, dict):
        test_desc = str(test_case.get("description") or "")
    return "{}||{}||{}||{}".format(test_desc, prompt_id or prompt_label, prompt_label, provider_id)


def _row_summary(row: Dict[str, Any]) -> Dict[str, Any]:
    prompt = row.get("prompt") or {}
    provider = row.get("provider") or {}
    test_case = row.get("testCase") or {}
    grading = row.get("gradingResult") or {}

    def _get(d: Any, key: str) -> Any:
        return d.get(key) if isinstance(d, dict) else None

    score = row.get("score")
    if score is None:
        score = _get(grading, "score")

    reason = row.get("error")
    if not reason:
        reason = _get(grading, "reason")

    return {
        "test": _get(test_case, "description") or "",
        "prompt_id": _get(prompt, "id") or "",
        "prompt_label": _get(prompt, "label") or "",
        "provider": _get(provider, "id") or "",
        "success": bool(row.get("success", False)),
        "score": float(score) if score is not None else None,
        "reason": str(reason or "")[:900],
    }


def _compare_promptfoo_outputs(*, baseline_path: Path, candidate_path: Path) -> Dict[str, Any]:
    def _load(path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        try:
            return json.loads(read_text(path))
        except Exception:
            return {}

    baseline_payload = _load(baseline_path)
    candidate_payload = _load(candidate_path)

    baseline_rows = {_row_key(r): r for r in _load_promptfoo_rows(baseline_payload)}
    candidate_rows = {_row_key(r): r for r in _load_promptfoo_rows(candidate_payload)}

    regressions: List[Dict[str, Any]] = []
    improvements: List[Dict[str, Any]] = []
    changed_score: List[Dict[str, Any]] = []
    unchanged_failures: List[Dict[str, Any]] = []
    unchanged_passes: List[Dict[str, Any]] = []
    missing_in_candidate: List[Dict[str, Any]] = []
    missing_in_baseline: List[Dict[str, Any]] = []

    all_keys = sorted(set(baseline_rows.keys()) | set(candidate_rows.keys()))
    for key in all_keys:
        b = baseline_rows.get(key)
        c = candidate_rows.get(key)
        if b is None and c is not None:
            missing_in_baseline.append(_row_summary(c))
            continue
        if c is None and b is not None:
            missing_in_candidate.append(_row_summary(b))
            continue
        if b is None or c is None:
            continue

        bs = bool(b.get("success", False))
        cs = bool(c.get("success", False))
        bsum = _row_summary(b)
        csum = _row_summary(c)

        if bs and not cs:
            regressions.append({"baseline": bsum, "candidate": csum})
        elif not bs and cs:
            improvements.append({"baseline": bsum, "candidate": csum})
        else:
            # 两边都通过或都失败
            bscore = bsum.get("score")
            cscore = csum.get("score")
            if bscore is not None and cscore is not None and abs(float(bscore) - float(cscore)) > 1e-9:
                changed_score.append({"baseline": bsum, "candidate": csum, "delta": float(cscore) - float(bscore)})
            if bs and cs:
                unchanged_passes.append({"baseline": bsum, "candidate": csum})
            else:
                unchanged_failures.append({"baseline": bsum, "candidate": csum})

    return {
        "baseline": {"evalId": baseline_payload.get("evalId"), "stats": ((baseline_payload.get("results") or {}).get("stats") or {})},
        "candidate": {"evalId": candidate_payload.get("evalId"), "stats": ((candidate_payload.get("results") or {}).get("stats") or {})},
        "diff": {
            "regressions": regressions,
            "improvements": improvements,
            "changed_score": changed_score,
            "unchanged_failures": unchanged_failures,
            "unchanged_passes": unchanged_passes,
            "missing_in_candidate": missing_in_candidate,
            "missing_in_baseline": missing_in_baseline,
        },
    }


def _run_promptfoo_agent_suite(*, root: Path, output_base_dir: Path, git_head: Optional[str], check: bool) -> int:
    config_dir = root / "agentdev/prompt-eval/promptfoo"
    ssot_config_path = config_dir / "promptfooconfig.agent.yaml"
    pinned_version_path = config_dir / "promptfoo-version.txt"

    agent_out_dir = output_base_dir / "agent"
    agent_out_dir.mkdir(parents=True, exist_ok=True)

    actual_version = _promptfoo_version()
    if actual_version is None:
        print("[错误] 找不到可执行的 `promptfoo` (请先在本机安装).", file=sys.stderr)
        return 2

    pinned_version = pinned_version_path.read_text(encoding="utf-8").strip() if pinned_version_path.exists() else ""
    if pinned_version and actual_version != pinned_version and environ.get("PROMPT_EVAL_PROMPTFOO_VERSION_ALLOW_ANY") != "1":
        print(
            "[错误] `promptfoo` 版本不匹配: 锁定={} 实际={}. (如需跳过,设置 `PROMPT_EVAL_PROMPTFOO_VERSION_ALLOW_ANY=1`)".format(
                pinned_version, actual_version
            ),
            file=sys.stderr,
        )
        return 2

    baseline_ref = str(environ.get("PROMPT_EVAL_LLM_BASELINE_REF") or "").strip()
    if baseline_ref:
        snapshots_dir = agent_out_dir / "snapshots"
        workspaces_dir = agent_out_dir / "workspaces"
        ab_dir = agent_out_dir / "ab"
        compare_path = ab_dir / "compare.json"

        if compare_path.exists():
            compare_path.unlink()
        if snapshots_dir.exists():
            shutil.rmtree(snapshots_dir)
        if workspaces_dir.exists():
            shutil.rmtree(workspaces_dir)

        try:
            candidate_skill_md = _materialize_skill_snapshot_candidate(root=root, dest_dir=snapshots_dir / "candidate")
            baseline_skill_md = _materialize_skill_snapshot_baseline(root=root, ref=baseline_ref, dest_dir=snapshots_dir / "baseline")
        except Exception as e:
            print("[错误] 无法生成技能快照: {}".format(e), file=sys.stderr)
            return 2

        baseline_replacements = _setup_agent_workspaces(
            root=root,
            workspaces_root=workspaces_dir / "baseline",
            skill_dir=baseline_skill_md.parent,
        )
        candidate_replacements = _setup_agent_workspaces(
            root=root,
            workspaces_root=workspaces_dir / "candidate",
            skill_dir=candidate_skill_md.parent,
        )

        baseline_cfg = ab_dir / "baseline/promptfooconfig.yaml"
        candidate_cfg = ab_dir / "candidate/promptfooconfig.yaml"
        try:
            _render_promptfoo_config_with_replacements(
                ssot_path=ssot_config_path, dest_path=baseline_cfg, replacements=baseline_replacements
            )
            _render_promptfoo_config_with_replacements(
                ssot_path=ssot_config_path, dest_path=candidate_cfg, replacements=candidate_replacements
            )
        except Exception as e:
            print("[错误] 无法渲染 `promptfoo` 配置: {}".format(e), file=sys.stderr)
            return 2

        rc_base, base_summary = _run_promptfoo_once(
            root=root,
            output_dir=ab_dir / "baseline",
            config_path=baseline_cfg,
            actual_version=actual_version,
            pinned_version=pinned_version or None,
            git_head=git_head,
            check=check,
            variant="baseline",
            baseline_ref=baseline_ref,
            skill_md_path=None,
        )
        rc_cand, cand_summary = _run_promptfoo_once(
            root=root,
            output_dir=ab_dir / "candidate",
            config_path=candidate_cfg,
            actual_version=actual_version,
            pinned_version=pinned_version or None,
            git_head=git_head,
            check=check,
            variant="candidate",
            baseline_ref=baseline_ref,
            skill_md_path=None,
        )

        if (ab_dir / "baseline/promptfoo-output.json").exists() and (ab_dir / "candidate/promptfoo-output.json").exists():
            payload = _compare_promptfoo_outputs(
                baseline_path=ab_dir / "baseline/promptfoo-output.json",
                candidate_path=ab_dir / "candidate/promptfoo-output.json",
            )
            payload["meta"] = {
                "baseline_ref": baseline_ref,
                "candidate_head": git_head,
                "promptfoo_version": actual_version,
                "promptfoo_pinned": pinned_version or None,
            }
            _write_json(compare_path, payload)

        top_summary: Dict[str, Any] = {
            "runner": {"name": _RUNNER_NAME, "version": _RUNNER_VERSION},
            "mode": "check" if check else "run",
            "git": {"head": git_head},
            "baseline_ref": baseline_ref,
            "variants": {
                "baseline": {
                    "summary": _rel_or_abs(ab_dir / "baseline/summary.json", root),
                    "output": _rel_or_abs(ab_dir / "baseline/promptfoo-output.json", root),
                },
                "candidate": {
                    "summary": _rel_or_abs(ab_dir / "candidate/summary.json", root),
                    "output": _rel_or_abs(ab_dir / "candidate/promptfoo-output.json", root),
                },
            },
            "compare": _rel_or_abs(compare_path, root) if compare_path.exists() else None,
            "ok": (rc_base == 0 and rc_cand == 0),
            "dry_run": environ.get("PROMPT_EVAL_LLM_DRY_RUN") == "1",
        }
        if base_summary:
            top_summary["baseline_summary"] = base_summary
        if cand_summary:
            top_summary["candidate_summary"] = cand_summary
        _write_json(agent_out_dir / "summary.json", top_summary)

        allow_failure = environ.get("PROMPT_EVAL_LLM_ALLOW_FAILURE") == "1"
        fatal = (rc_base == 2) or (rc_cand == 2)
        if fatal:
            return 2
        if (rc_base != 0 or rc_cand != 0) and not allow_failure:
            return 1
        return 0

    # 仅候选模式。
    snapshots_dir = agent_out_dir / "snapshots"
    workspaces_dir = agent_out_dir / "workspaces"
    if snapshots_dir.exists():
        shutil.rmtree(snapshots_dir)
    if workspaces_dir.exists():
        shutil.rmtree(workspaces_dir)

    try:
        candidate_skill_md = _materialize_skill_snapshot_candidate(root=root, dest_dir=snapshots_dir / "candidate")
    except Exception as e:
        print("[错误] 无法生成技能快照: {}".format(e), file=sys.stderr)
        return 2

    replacements = _setup_agent_workspaces(
        root=root,
        workspaces_root=workspaces_dir / "candidate",
        skill_dir=candidate_skill_md.parent,
    )
    rendered_cfg = agent_out_dir / "promptfooconfig.yaml"
    try:
        _render_promptfoo_config_with_replacements(ssot_path=ssot_config_path, dest_path=rendered_cfg, replacements=replacements)
    except Exception as e:
        print("[错误] 无法渲染 `promptfoo` 配置: {}".format(e), file=sys.stderr)
        return 2

    rc, _summary = _run_promptfoo_once(
        root=root,
        output_dir=agent_out_dir,
        config_path=rendered_cfg,
        actual_version=actual_version,
        pinned_version=pinned_version or None,
        git_head=git_head,
        check=check,
        variant="candidate",
        baseline_ref=None,
        skill_md_path=None,
    )

    allow_failure = environ.get("PROMPT_EVAL_LLM_ALLOW_FAILURE") == "1"
    if rc != 0 and not allow_failure:
        if rc == 2:
            return 2
        return 1
    return 0


def _run_promptfoo_llm_suite(*, root: Path, output_base_dir: Path, git_head: Optional[str], check: bool) -> int:
    config_dir = root / "agentdev/prompt-eval/promptfoo"
    ssot_config_path = config_dir / "promptfooconfig.yaml"
    pinned_version_path = config_dir / "promptfoo-version.txt"

    llm_out_dir = output_base_dir / "llm"
    llm_out_dir.mkdir(parents=True, exist_ok=True)

    actual_version = _promptfoo_version()
    if actual_version is None:
        print("[错误] 找不到可执行的 `promptfoo` (请先在本机安装).", file=sys.stderr)
        return 2

    pinned_version = pinned_version_path.read_text(encoding="utf-8").strip() if pinned_version_path.exists() else ""
    if pinned_version and actual_version != pinned_version and environ.get("PROMPT_EVAL_PROMPTFOO_VERSION_ALLOW_ANY") != "1":
        print(
            "[错误] `promptfoo` 版本不匹配: 锁定={} 实际={}. (如需跳过,设置 `PROMPT_EVAL_PROMPTFOO_VERSION_ALLOW_ANY=1`)".format(
                pinned_version, actual_version
            ),
            file=sys.stderr,
        )
        return 2

    baseline_ref = str(environ.get("PROMPT_EVAL_LLM_BASELINE_REF") or "").strip()
    if baseline_ref:
        snapshots_dir = llm_out_dir / "snapshots"
        ab_dir = llm_out_dir / "ab"
        compare_path = ab_dir / "compare.json"

        if compare_path.exists():
            compare_path.unlink()

        if snapshots_dir.exists():
            shutil.rmtree(snapshots_dir)

        try:
            candidate_skill_md = _materialize_skill_snapshot_candidate(root=root, dest_dir=snapshots_dir / "candidate")
            baseline_skill_md = _materialize_skill_snapshot_baseline(root=root, ref=baseline_ref, dest_dir=snapshots_dir / "baseline")
        except Exception as e:
            print("[错误] 无法生成技能快照: {}".format(e), file=sys.stderr)
            return 2

        baseline_cfg = ab_dir / "baseline/promptfooconfig.yaml"
        candidate_cfg = ab_dir / "candidate/promptfooconfig.yaml"

        try:
            _render_promptfoo_config_for_skill(ssot_path=ssot_config_path, dest_path=baseline_cfg, skill_md_path=baseline_skill_md)
            _render_promptfoo_config_for_skill(ssot_path=ssot_config_path, dest_path=candidate_cfg, skill_md_path=candidate_skill_md)
        except Exception as e:
            print("[错误] 无法渲染 `promptfoo` 配置: {}".format(e), file=sys.stderr)
            return 2

        rc_base, base_summary = _run_promptfoo_once(
            root=root,
            output_dir=ab_dir / "baseline",
            config_path=baseline_cfg,
            actual_version=actual_version,
            pinned_version=pinned_version or None,
            git_head=git_head,
            check=check,
            variant="baseline",
            baseline_ref=baseline_ref,
            skill_md_path=baseline_skill_md,
        )
        rc_cand, cand_summary = _run_promptfoo_once(
            root=root,
            output_dir=ab_dir / "candidate",
            config_path=candidate_cfg,
            actual_version=actual_version,
            pinned_version=pinned_version or None,
            git_head=git_head,
            check=check,
            variant="candidate",
            baseline_ref=baseline_ref,
            skill_md_path=candidate_skill_md,
        )

        if (ab_dir / "baseline/promptfoo-output.json").exists() and (ab_dir / "candidate/promptfoo-output.json").exists():
            payload = _compare_promptfoo_outputs(
                baseline_path=ab_dir / "baseline/promptfoo-output.json",
                candidate_path=ab_dir / "candidate/promptfoo-output.json",
            )
            payload["meta"] = {
                "baseline_ref": baseline_ref,
                "candidate_head": git_head,
                "promptfoo_version": actual_version,
                "promptfoo_pinned": pinned_version or None,
            }
            _write_json(compare_path, payload)

        top_summary: Dict[str, Any] = {
            "runner": {"name": _RUNNER_NAME, "version": _RUNNER_VERSION},
            "mode": "check" if check else "run",
            "git": {"head": git_head},
            "baseline_ref": baseline_ref,
            "variants": {
                "baseline": {
                    "summary": _rel_or_abs(ab_dir / "baseline/summary.json", root),
                    "output": _rel_or_abs(ab_dir / "baseline/promptfoo-output.json", root),
                },
                "candidate": {
                    "summary": _rel_or_abs(ab_dir / "candidate/summary.json", root),
                    "output": _rel_or_abs(ab_dir / "candidate/promptfoo-output.json", root),
                },
            },
            "compare": _rel_or_abs(compare_path, root) if compare_path.exists() else None,
            "ok": (rc_base == 0 and rc_cand == 0),
            "dry_run": environ.get("PROMPT_EVAL_LLM_DRY_RUN") == "1",
        }
        if base_summary:
            top_summary["baseline_summary"] = base_summary
        if cand_summary:
            top_summary["candidate_summary"] = cand_summary
        _write_json(llm_out_dir / "summary.json", top_summary)

        allow_failure = environ.get("PROMPT_EVAL_LLM_ALLOW_FAILURE") == "1"
        fatal = (rc_base == 2) or (rc_cand == 2)
        if fatal:
            return 2
        if (rc_base != 0 or rc_cand != 0) and not allow_failure:
            return 1
        return 0

    rc, summary = _run_promptfoo_once(
        root=root,
        output_dir=llm_out_dir,
        config_path=ssot_config_path,
        actual_version=actual_version,
        pinned_version=pinned_version or None,
        git_head=git_head,
        check=check,
        variant=None,
        baseline_ref=None,
        skill_md_path=None,
    )

    if summary:
        _write_json(llm_out_dir / "summary.json", summary)

    allow_failure = environ.get("PROMPT_EVAL_LLM_ALLOW_FAILURE") == "1"
    if rc != 0 and not allow_failure:
        if rc == 2:
            return 2
        return 1
    return 0


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
        "--cases-root", default="agentdev/prompt-eval/cases", help="Cases root directory (default: agentdev/prompt-eval/cases)"
    )
    parser.add_argument("--output-dir", default=".tmp/artifacts/prompt-eval", help="Output directory (default: .tmp/artifacts/prompt-eval)")
    parser.add_argument("--check", action="store_true", help="CI mode: deterministic core only")
    parser.add_argument("--llm", action="store_true", help="Enable optional LLM suite (requires extra tooling; not enabled by default)")
    parser.add_argument("--llm-agent", action="store_true", help="Enable optional LLM agent suite (promptfoo + coding agent; expensive)")
    args = parser.parse_args(list(argv) if argv is not None else None)

    root = _repo_root()
    cases_root = root / args.cases_root
    out_dir = root / args.output_dir

    if args.llm and args.llm_agent:
        print("[错误] `--llm` 与 `--llm-agent` 互斥,请只选一个.", file=sys.stderr)
        return 2

    if args.llm_agent:
        head = _git_head(root)
        return _run_promptfoo_agent_suite(root=root, output_base_dir=out_dir, git_head=head, check=args.check)

    if args.llm:
        head = _git_head(root)
        return _run_promptfoo_llm_suite(root=root, output_base_dir=out_dir, git_head=head, check=args.check)

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
