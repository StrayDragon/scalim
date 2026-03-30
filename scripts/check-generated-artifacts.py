import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _manifest_path(repo_root: Path) -> Path:
    return repo_root / "openspec" / "ssot" / "generated_artifacts_manifest.json"


def _load_manifest(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _as_list(value: object) -> List[object]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    raise TypeError("期望为 `list`, 实际为 `{}`".format(type(value).__name__))


def _expand_globs(repo_root: Path, patterns: Sequence[str]) -> List[str]:
    """将仓库相对路径的 `glob` 模式展开为去重、排序后的文件列表(仍为仓库相对路径)."""

    out: List[str] = []
    for pattern in patterns:
        pat = str(pattern or "").strip()
        if not pat:
            continue
        if "*" in pat or "?" in pat or "[" in pat:
            matches = repo_root.glob(pat)
        else:
            matches = [repo_root / pat]
        for match in matches:
            try:
                rel = match.resolve().relative_to(repo_root.resolve())
            except Exception:  # noqa: BLE001
                continue
            if match.is_file():
                out.append(rel.as_posix())
    return sorted(set(out))


def _path_matches_any_glob(path: str, patterns: Sequence[str]) -> bool:
    for pat in patterns:
        pat_text = str(pat or "").strip()
        if not pat_text:
            continue
        # 说明: `pathlib.PurePath.match` 不会将 `**` 视为“任意深度匹配”；
        # 漂移检查与 `manifest` 使用 `shell` 风格的 `glob`(包含 `**`),因此这里使用 `fnmatch`.
        if fnmatch.fnmatch(path, pat_text):
            return True
    return False


def _git_ls_files(repo_root: Path) -> List[str]:
    proc = subprocess.run(
        ["git", "ls-files"],
        cwd=str(repo_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError("`git ls-files` 失败: {}".format(proc.stderr.strip()))
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _git_diff_exit_code(repo_root: Path, files: Sequence[str]) -> int:
    args = ["git", "diff", "--exit-code", "--"]
    args.extend([str(x) for x in files])
    proc = subprocess.run(
        args,
        cwd=str(repo_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return int(proc.returncode)


def _run_python_script(repo_root: Path, script: str, args: Sequence[str]) -> int:
    script_path = repo_root / str(script)
    proc = subprocess.run(
        [sys.executable, str(script_path), *list(args)],
        cwd=str(repo_root),
    )
    return int(proc.returncode)


def _validate_group(group: Dict[str, Any]) -> Tuple[str, List[str], Dict[str, Any], str]:
    group_id = str(group.get("id", "") or "").strip()
    if not group_id:
        raise ValueError("`manifest.groups[].id` 为必填项")

    generated_globs = [str(x) for x in _as_list(group.get("generated_globs"))]
    if not generated_globs:
        raise ValueError("`manifest.groups[{}].generated_globs` 为必填项".format(group_id))

    check = group.get("check")
    if not isinstance(check, dict):
        raise ValueError("`manifest.groups[{}].check` 必须是对象".format(group_id))

    fix = str(group.get("fix", "") or "").strip()
    if not fix:
        raise ValueError("`manifest.groups[{}].fix` 为必填项".format(group_id))

    return group_id, generated_globs, check, fix


def _candidate_generated_files(tracked_files: Sequence[str]) -> List[str]:
    # 约定: 任何被 `git` 跟踪且包含 `.gen.` 的文件都视为生成物候选.
    return [p for p in tracked_files if ".gen." in p]


def _unclaimed_generated_files(tracked_files: Sequence[str], claimed_globs: Sequence[str]) -> List[str]:
    candidates = _candidate_generated_files(tracked_files)
    out: List[str] = []
    for path in candidates:
        if not _path_matches_any_glob(path, claimed_globs):
            out.append(path)
    return sorted(out)


def _check_groups(repo_root: Path, manifest: Dict[str, Any], *, only: Optional[Sequence[str]]) -> int:
    raw_groups = _as_list(manifest.get("groups"))
    groups: List[Tuple[str, List[str], Dict[str, Any], str]] = []
    for item in raw_groups:
        if not isinstance(item, dict):
            raise ValueError("`manifest.groups` 必须是对象列表")
        groups.append(_validate_group(item))

    only_set: Optional[set] = None
    if only:
        only_set = set(str(x).strip() for x in only if str(x).strip())

    failures: List[str] = []

    for group_id, generated_globs, check, fix in groups:
        if only_set is not None and group_id not in only_set:
            continue

        kind = str(check.get("kind", "") or "").strip()
        if kind == "python_script":
            script = str(check.get("script", "") or "").strip()
            args = [str(x) for x in _as_list(check.get("args"))]
            if not script:
                raise ValueError("`manifest.groups[{}].check.script` 为必填项".format(group_id))
            code = _run_python_script(repo_root, script, args)
            if code != 0:
                failures.append("[{}] 生成物漂移/校验失败 (修复: {})".format(group_id, fix))
            continue

        if kind == "generate_and_git_diff":
            generate_steps = _as_list(check.get("generate"))
            diff_globs = [str(x) for x in _as_list(check.get("diff_globs"))]
            if not generate_steps:
                raise ValueError("`manifest.groups[{}].check.generate` 为必填项".format(group_id))
            if not diff_globs:
                raise ValueError("`manifest.groups[{}].check.diff_globs` 为必填项".format(group_id))

            for step in generate_steps:
                if not isinstance(step, dict):
                    raise ValueError("`manifest.groups[{}].check.generate` 必须是对象列表".format(group_id))
                script = str(step.get("script", "") or "").strip()
                args = [str(x) for x in _as_list(step.get("args"))]
                if not script:
                    raise ValueError("`manifest.groups[{}].check.generate[].script` 为必填项".format(group_id))
                code = _run_python_script(repo_root, script, args)
                if code != 0:
                    failures.append("[{}] 生成步骤失败: {} (修复: {})".format(group_id, script, fix))
                    break
            else:
                diff_files = _expand_globs(repo_root, diff_globs)
                if not diff_files:
                    raise ValueError("`manifest.groups[{}].check.diff_globs` 未匹配到任何文件".format(group_id))
                diff_code = _git_diff_exit_code(repo_root, diff_files)
                if diff_code != 0:
                    failures.append("[{}] 检测到生成物漂移 (修复: {})".format(group_id, fix))
            continue

        raise ValueError("未知的 `manifest.groups[{}].check.kind`: {!r}".format(group_id, kind))

    if failures:
        for line in failures:
            print(line, file=sys.stderr)
        return 1
    return 0


def _check_manifest_claims_all_generated(repo_root: Path, manifest: Dict[str, Any]) -> int:
    raw_groups = _as_list(manifest.get("groups"))
    claimed_globs: List[str] = []
    for item in raw_groups:
        if not isinstance(item, dict):
            continue
        claimed_globs.extend([str(x) for x in _as_list(item.get("generated_globs"))])

    tracked = _git_ls_files(repo_root)
    unclaimed = _unclaimed_generated_files(tracked, claimed_globs)
    if not unclaimed:
        return 0

    print("检测到新增生成物但未登记 `manifest` (SSOT: `openspec/ssot/generated_artifacts_manifest.json`):", file=sys.stderr)
    for path in unclaimed[:50]:
        print("  - {}".format(path), file=sys.stderr)
    if len(unclaimed) > 50:
        print("  ... (还有 {} 条)".format(len(unclaimed) - 50), file=sys.stderr)
    print("修复: 更新 `openspec/ssot/generated_artifacts_manifest.json` 覆盖这些生成物路径/规则.", file=sys.stderr)
    return 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="检查受控生成物漂移 (SSOT=`generated_artifacts_manifest`).")
    parser.add_argument("--check", action="store_true", help="执行检查并在漂移时直接失败.")
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        help="仅检查指定 `group_id` (可重复). 例如: `--only docs-site --only yaml-dsl-schema`",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    if not args.check:
        parser.error("必须使用 `--check`")

    repo_root = _repo_root()
    manifest_file = _manifest_path(repo_root)
    manifest = _load_manifest(manifest_file)

    group_code = _check_groups(repo_root, manifest, only=list(args.only) if args.only else None)
    claims_code = _check_manifest_claims_all_generated(repo_root, manifest)
    return 1 if (group_code != 0 or claims_code != 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
