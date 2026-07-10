#!/usr/bin/env python3
"""
`pre-commit` 门禁: 对照 `sanitize` 规则检查 `git staged` 变更.

读取 `llmanspec/sanitize_rules.yaml` 与 `llmanspec/sanitize_rules.local.yaml`,
再对 `staged` 变更中所有新增/修改行做模式匹配.

用法:
  `python scripts/check-staged-sanitize.py`         # 检查 `staged` 变更
  `python scripts/check-staged-sanitize.py --diff`   # 从 `stdin` 读取 `diff`

退出码:
  `0`  → 未检测到泄漏
  `1`  → 检测到泄漏
  `2`  → 错误(缺少规则等)
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple


def _load_rules(repo_root: Path) -> List[Tuple[str, re.Pattern, str]]:
    """从 `sanitize_rules.yaml` 与本地 `overlay` 加载规则."""

    # 优先用 `scalim` 内置 `yaml`,失败再回退 `stdlib`
    try:
        from scalim.vendor.yamlx import yaml as _yaml
    except ImportError:
        import yaml as _yaml  # type: ignore[no-redef]

    rules_file = repo_root / "llmanspec" / "sanitize_rules.yaml"
    local_file = repo_root / "llmanspec" / "sanitize_rules.local.yaml"

    all_rules: Dict[str, Tuple[str, re.Pattern, str]] = {}

    for path in [rules_file, local_file]:
        if not path.is_file():
            continue
        data = _yaml.safe_load(path.read_text(encoding="utf-8"))
        for entry in (data or {}).get("rules", []):
            name = str(entry.get("name", "?"))
            pattern = str(entry.get("pattern", ""))
            replace = str(entry.get("replace", ""))
            try:
                regex = re.compile(pattern)
            except re.error as exc:
                print(
                    f"[warn] skipping rule {name!r}: bad regex {pattern!r}: {exc}",  # force-en
                    file=sys.stderr,
                )
                continue
            # 本地 `overlay` 同名规则覆盖公共规则
            all_rules[name] = (name, regex, replace)

    return list(all_rules.values())


def _get_staged_diff() -> str:
    """返回 `staged` 变更的 `unified diff`(新增/修改/重命名文件)."""
    result = subprocess.run(
        ["git", "diff", "--staged", "--diff-filter=ACMR", "--"],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    if result.returncode != 0:
        print(f"[error] git diff --staged failed:\n{result.stderr}", file=sys.stderr)  # force-en
        sys.exit(2)
    return result.stdout


def _is_textual(path: str) -> bool:
    """启发式: 跳过已知二进制路径."""
    skip_exts = frozenset(
        {
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".bmp",
            ".ico",
            ".pdf",
            ".doc",
            ".docx",
            ".xls",
            ".xlsx",
            ".zip",
            ".tar",
            ".gz",
            ".bz2",
            ".7z",
            ".rar",
            ".so",
            ".dll",
            ".dylib",
            ".exe",
            ".woff",
            ".woff2",
            ".ttf",
            ".eot",
            ".mp3",
            ".mp4",
            ".avi",
            ".mov",
            ".o",
            ".a",
            ".lib",
            ".pyc",
            ".pyo",
            ".svgz",
        }
    )
    return Path(path).suffix.lower() not in skip_exts


_SELF_SKIP = frozenset(
    {
        "scripts/sanitize.py",
        "scripts/check-staged-sanitize.py",
        "llmanspec/sanitize_rules.yaml",
        "llmanspec/sanitize_rules.local.yaml",
        "llmanspec/sanitize_rules.local.example.yaml",
    }
)


def check_diff(diff_text: str, rules: List[Tuple[str, re.Pattern, str]]) -> int:
    """
    对照规则扫描 `diff` 行,泄漏信息打印到 `stderr`.

    返回泄漏条数.
    """
    leaks: Dict[str, List[Tuple[str, str, int]]] = defaultdict(list)
    # ^ `file_path` -> [(`rule_name`, `matched_text`, `approx_line`)]

    current_file = ""
    for line in diff_text.splitlines():
        # 跟踪文件头
        if line.startswith("+++ b/"):
            current_file = line[6:]
            if not _is_textual(current_file) or current_file in _SELF_SKIP:
                current_file = ""
            continue
        if not current_file:
            continue

        # 只看新增行
        if not line.startswith("+"):
            continue
        # 跳过 `diff` 元数据
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            continue

        content = line[1:]  # 去掉行首 `+`
        for rule_name, regex, _replace in rules:
            for match in regex.finditer(content):
                leaks[current_file].append((rule_name, match.group(), 0))

    # 报告
    if not leaks:
        return 0

    print(f"\n{'=' * 60}", file=sys.stderr)
    print("❌  SANITIZE LEAK(S) DETECTED IN STAGED CHANGES", file=sys.stderr)  # force-en
    print(f"{'=' * 60}", file=sys.stderr)

    total = 0
    for fpath in sorted(leaks):
        print(f"\n  📁 {fpath}", file=sys.stderr)
        for rule_name, matched, _ in leaks[fpath]:
            print(f"     ⚠️  [{rule_name}] {matched!r}", file=sys.stderr)
            total += 1

    print(f"\n{'=' * 60}", file=sys.stderr)
    print(f"Total: {total} leak(s) in {len(leaks)} file(s)", file=sys.stderr)  # force-en
    print(f"{'=' * 60}\n", file=sys.stderr)
    return total


def main() -> int:
    repo_root = Path.cwd()

    rules = _load_rules(repo_root)
    if not rules:
        print("[error] no sanitize rules loaded", file=sys.stderr)  # force-en
        return 2

    print(
        f"🔍 Checking staged changes against {len(rules)} sanitize rule(s)...",  # force-en
        file=sys.stderr,
    )

    diff_text = _get_staged_diff()
    if not diff_text.strip():
        print("   No staged changes to check.", file=sys.stderr)  # force-en
        return 0

    leak_count = check_diff(diff_text, rules)
    if leak_count == 0:
        print("✅  No leaks detected in staged changes.", file=sys.stderr)  # force-en
        return 0

    print(
        "💡  Tip: run `just llmanspec-sanitize` to auto-apply replacements.",  # force-en
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
