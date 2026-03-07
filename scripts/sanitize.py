from __future__ import annotations

import argparse
import dataclasses
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

import yaml


@dataclasses.dataclass(frozen=True)
class _Rule:
    name: str
    pattern: str
    replace: str
    regex: re.Pattern[str]


_TEXT_EXTS = {
    ".md",
    ".markdown",
    ".yaml",
    ".yml",
    ".json",
    ".py",
    ".js",
    ".ts",
    ".sh",
    ".txt",
    ".toml",
    ".ini",
}

_SKIPPED_RULE_FILES = {
    "sanitize.py",
    "sanitize_rules.yaml",
    "sanitize_rules.local.yaml",
    "sanitize_rules.local.example.yaml",
}


def _iter_target_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.name in _SKIPPED_RULE_FILES:
            continue
        if path.name == ".gitkeep":
            continue
        if path.suffix.lower() not in _TEXT_EXTS:
            continue
        yield path


def _load_rules(rules_path: Path) -> List[_Rule]:
    raw = yaml.safe_load(rules_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "rules" not in raw:
        raise ValueError("规则文件无效：缺少顶层 `rules` 字段")
    items = raw["rules"]
    if not isinstance(items, list):
        raise ValueError("规则文件无效：`rules` 必须是列表")

    rules: List[_Rule] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("规则项无效（不是映射）：{}".format(item))
        name = str(item.get("name") or "").strip()
        pattern = str(item.get("pattern") or "")
        replace = str(item.get("replace") or "")
        if not name:
            raise ValueError("规则项无效：缺少 `name`")
        try:
            regex = re.compile(pattern)
        except re.error as exc:
            raise ValueError("规则 {} 的正则无效：{}".format(name, exc)) from exc
        rules.append(_Rule(name=name, pattern=pattern, replace=replace, regex=regex))
    return rules


def _load_rules_from_paths(rule_paths: Iterable[Path]) -> List[_Rule]:
    rules: List[_Rule] = []
    for rules_path in rule_paths:
        rules.extend(_load_rules(rules_path))
    return rules


def _apply_rules_to_text(text: str, rules: List[_Rule]) -> Tuple[str, Counter[str]]:
    counts: Counter[str] = Counter()
    out = text
    for rule in rules:
        out, n = rule.regex.subn(rule.replace, out)
        if n:
            counts[rule.name] += n
    return out, counts


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sanitize a target directory for public release.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Report matches without modifying files.")
    mode.add_argument("--apply", action="store_true", help="Apply sanitization in-place.")
    parser.add_argument(
        "--root",
        help="Target directory to sanitize (default: repo's openspec/ when present).",
    )
    parser.add_argument(
        "--rules",
        help=(
            "Base public rules file path. Defaults to searching from --root upward for "
            "sanitize_rules.yaml, then falling back to the repo default."
        ),
    )
    parser.add_argument(
        "--local-rules",
        help=(
            "Optional local private rules file. Defaults to searching from --root upward for "
            "sanitize_rules.local.yaml, then falling back to the repo default."
        ),
    )
    parser.add_argument(
        "--no-local-rules",
        action="store_true",
        help="Disable auto-loading the local private rules file.",
    )
    parser.add_argument(
        "--extra-rules",
        action="append",
        default=[],
        help="Optional additional rules files loaded before the public rules.",
    )
    return parser.parse_args()


def _iter_search_roots(root: Path, repo_root: Path) -> Iterator[Path]:
    current = root
    while True:
        yield current
        if current == repo_root:
            break
        current = current.parent


def _find_default_rule_path(filename: str, root: Path, repo_root: Path) -> Optional[Path]:
    for base in _iter_search_roots(root, repo_root):
        candidate = base / filename
        if candidate.exists():
            return candidate.resolve()
    return None


def _resolve_rule_path(explicit_path: Optional[str], filename: str, root: Path, repo_root: Path) -> Optional[Path]:
    if explicit_path:
        return Path(explicit_path).resolve()
    return _find_default_rule_path(filename, root, repo_root)


def _dedupe_paths(paths: Iterable[Path]) -> List[Path]:
    unique_paths: List[Path] = []
    seen = set()
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        unique_paths.append(path)
        seen.add(key)
    return unique_paths


def _resolve_rule_paths(args: argparse.Namespace, root: Path, repo_root: Path) -> List[Path]:
    rule_paths: List[Path] = []

    if not args.no_local_rules:
        local_rules_path = _resolve_rule_path(args.local_rules, "sanitize_rules.local.yaml", root, repo_root)
        if local_rules_path is not None:
            rule_paths.append(local_rules_path)

    for extra_rule in args.extra_rules:
        rule_paths.append(Path(extra_rule).resolve())

    rules_path = _resolve_rule_path(args.rules, "sanitize_rules.yaml", root, repo_root)
    if rules_path is None:
        return []
    rule_paths.append(rules_path)
    return _dedupe_paths(rule_paths)


def main() -> int:
    args = _parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    default_root = repo_root / "openspec"
    root = Path(args.root).resolve() if args.root else (default_root if default_root.exists() else repo_root)

    if not root.exists() or not root.is_dir():
        print("未找到根目录：{}".format(root), file=sys.stderr)
        return 2
    try:
        root.relative_to(repo_root)
    except ValueError:
        print("根目录必须位于仓库内：{}".format(repo_root), file=sys.stderr)
        return 2

    rule_paths = _resolve_rule_paths(args, root, repo_root)
    if not rule_paths:
        print("未找到规则文件：已从 {} 向上搜索 `sanitize_rules.yaml`".format(root), file=sys.stderr)
        return 2
    for path in rule_paths:
        if not path.exists():
            print("未找到规则文件：{}".format(path), file=sys.stderr)
            return 2

    rules = _load_rules_from_paths(rule_paths)

    rule_total: Counter[str] = Counter()
    file_hits: Dict[str, Counter[str]] = defaultdict(Counter)
    changed_files: List[Path] = []

    for path in _iter_target_files(root):
        try:
            original = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            original = path.read_text(encoding="utf-8", errors="replace")

        updated, counts = _apply_rules_to_text(original, rules)
        if counts:
            rule_total.update(counts)
            for rule_name, n in counts.items():
                file_hits[rule_name][str(path)] += n

        if args.apply and updated != original:
            path.write_text(updated, encoding="utf-8")
            changed_files.append(path)

    print("清理根目录：{}".format(root))
    print("规则文件：")
    for path in rule_paths:
        print("- {}".format(path))
    print("")

    if not rule_total:
        print("未发现匹配项。")
    else:
        print("规则命中汇总：")
        for name, n in rule_total.most_common():
            print("- {}: {}".format(name, n))
        print("")
        print("各规则命中文件（最多 10 个）：")
        for rule_name, hits in sorted(file_hits.items(), key=lambda kv: (-rule_total[kv[0]], kv[0])):
            top = hits.most_common(10)
            joined = ", ".join(["{}({})".format(p, n) for p, n in top])
            print("- {}: {}".format(rule_name, joined))

    if args.apply:
        print("")
        print("已修改文件数：{}".format(len(changed_files)))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
