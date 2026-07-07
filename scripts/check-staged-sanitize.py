#!/usr/bin/env python3
"""
Pre-commit gate: check git staged changes against sanitize rules.

Reads `llmanspec/sanitize_rules.yaml` and `llmanspec/sanitize_rules.local.yaml`,
then checks all added/modified lines in staged changes against the patterns.

Usage:
  python scripts/check-staged-sanitize.py         # check staged changes
  python scripts/check-staged-sanitize.py --diff   # read diff from stdin

Exit codes:
  0  → no leaks detected
  1  → leaks detected
  2  → error (missing rules, etc.)
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple


def _load_rules(repo_root: Path) -> List[Tuple[str, re.Pattern, str]]:
    """Load rules from sanitize_rules.yaml and the local overlay."""

    # Try scalim's vendored yaml first, fallback to stdlib
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
                    f"[warn] skipping rule {name!r}: bad regex {pattern!r}: {exc}",
                    file=sys.stderr,
                )
                continue
            # Local overlay replaces the public rule with same name
            all_rules[name] = (name, regex, replace)

    return list(all_rules.values())


def _get_staged_diff() -> str:
    """Return unified diff of staged changes (added/modified/renamed files)."""
    result = subprocess.run(
        ["git", "diff", "--staged", "--diff-filter=ACMR", "--"],
        capture_output=True, text=True,
        cwd=Path.cwd(),
    )
    if result.returncode != 0:
        print(f"[error] git diff --staged failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(2)
    return result.stdout


def _is_textual(path: str) -> bool:
    """Heuristic: skip known-binary paths."""
    skip_exts = frozenset({
        ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico",
        ".pdf", ".doc", ".docx", ".xls", ".xlsx",
        ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
        ".so", ".dll", ".dylib", ".exe",
        ".woff", ".woff2", ".ttf", ".eot",
        ".mp3", ".mp4", ".avi", ".mov",
        ".o", ".a", ".lib", ".pyc", ".pyo",
        ".svgz",
    })
    return Path(path).suffix.lower() not in skip_exts


_SELF_SKIP = frozenset({
    "scripts/sanitize.py",
    "scripts/check-staged-sanitize.py",
    "llmanspec/sanitize_rules.yaml",
    "llmanspec/sanitize_rules.local.yaml",
    "llmanspec/sanitize_rules.local.example.yaml",
})


def check_diff(diff_text: str, rules: List[Tuple[str, re.Pattern, str]]) -> int:
    """
    Scan diff lines against rules. Prints leaks to stderr.

    Returns leak count.
    """
    leaks: Dict[str, List[Tuple[str, str, int]]] = defaultdict(list)
    # ^ file_path -> [(rule_name, matched_text, approx_line)]

    current_file = ""
    for line in diff_text.splitlines():
        # Track file header
        if line.startswith("+++ b/"):
            current_file = line[6:]
            if not _is_textual(current_file) or current_file in _SELF_SKIP:
                current_file = ""
            continue
        if not current_file:
            continue

        # Only added lines
        if not line.startswith("+"):
            continue
        # Skip diff metadata
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            continue

        content = line[1:]  # strip the leading +
        for rule_name, regex, _replace in rules:
            for match in regex.finditer(content):
                leaks[current_file].append((rule_name, match.group(), 0))

    # Report
    if not leaks:
        return 0

    print(f"\n{'=' * 60}", file=sys.stderr)
    print("❌  SANITIZE LEAK(S) DETECTED IN STAGED CHANGES", file=sys.stderr)
    print(f"{'=' * 60}", file=sys.stderr)

    total = 0
    for fpath in sorted(leaks):
        print(f"\n  📁 {fpath}", file=sys.stderr)
        for rule_name, matched, _ in leaks[fpath]:
            print(f"     ⚠️  [{rule_name}] {matched!r}", file=sys.stderr)
            total += 1

    print(f"\n{'=' * 60}", file=sys.stderr)
    print(f"Total: {total} leak(s) in {len(leaks)} file(s)", file=sys.stderr)
    print(f"{'=' * 60}\n", file=sys.stderr)
    return total


def main() -> int:
    repo_root = Path.cwd()

    rules = _load_rules(repo_root)
    if not rules:
        print("[error] no sanitize rules loaded", file=sys.stderr)
        return 2

    print(
        f"🔍 Checking staged changes against {len(rules)} sanitize rule(s)...",
        file=sys.stderr,
    )

    diff_text = _get_staged_diff()
    if not diff_text.strip():
        print("   No staged changes to check.", file=sys.stderr)
        return 0

    leak_count = check_diff(diff_text, rules)
    if leak_count == 0:
        print("✅  No leaks detected in staged changes.", file=sys.stderr)
        return 0

    print(
        "💡  Tip: run `just llmanspec-sanitize` to auto-apply replacements.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
