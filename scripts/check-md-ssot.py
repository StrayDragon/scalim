# ruff: noqa: T201
from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Pattern, Tuple


@dataclass(frozen=True)
class _Rule:
    name: str
    pattern: Pattern[str]
    message: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def _git_ls_files(root: Path, pattern: str) -> List[str]:
    try:
        output = subprocess.check_output(["git", "-C", str(root), "ls-files", pattern], text=True)
    except Exception as exc:
        raise RuntimeError("通过 `git` 列出 `Markdown` 文件失败: {}".format(exc)) from exc
    return [line.strip().replace("\\", "/") for line in output.splitlines() if line.strip()]


def _is_allowed_markdown(rel_posix: str) -> bool:
    # 迁移/历史区域允许保留旧写法(辅助作者升级或回溯)
    if rel_posix.startswith("agentdev/skills/scalim-yaml-dsl/references/upgrades/"):
        return True
    if rel_posix == "agentdev/skills/scalim-yaml-dsl/references/syntax-catalog.gen.md":
        return True
    if rel_posix == "agentdev/skills/scalim-yaml-dsl/references/generated/yaml-dsl-upgrades.gen.md":
        return True
    if rel_posix.startswith("llmanspec/changes/archive/"):
        return True
    return False


def _rules() -> Tuple[_Rule, ...]:
    return (
        _Rule(
            name="legacy-workflow-writes",
            pattern=re.compile(r"workflow\.runs\[\*\]\.writes"),
            message="已移除旧写法 `workflow.runs[*].writes`: 使用 `workflow.resources.books` + `demand` 输出的 `to/write` 绑定.",
        ),
        _Rule(
            name="legacy-workflow-resources-groups",
            pattern=re.compile(r"workflow\.resources\.(workbooks|csvs|sheetbooks)\b"),
            message="已移除旧写法 `workflow.resources.workbooks/csvs/sheetbooks`: 使用 `workflow.resources.books`.",
        ),
        _Rule(
            name="legacy-writes-output",
            pattern=re.compile(r"writes\[\*\]\.output\b"),
            message="已移除旧写法 `writes[*].output`: 使用 `demand` 输出的 `to/write` 绑定(并配合 Python `ResourcesPolicy`/`BookWritePolicy`).",
        ),
        _Rule(
            name="legacy-write-to",
            pattern=re.compile(r"\bwrite_to\b"),
            message="已移除字段 `write_to`: 使用 `demand` 输出的 `to/write` 绑定.",
        ),
        _Rule(
            name="legacy-sheetbook-loader-id",
            pattern=re.compile(r"workflow/sheetbook_sheet_rows"),
            message="已移除可调用 id `^workflow/sheetbook_sheet_rows`: 使用 `^workflow/book_sheet_rows`.",
        ),
        _Rule(
            name="legacy-sheetbook-loader",
            pattern=re.compile(r"\bsheetbook_sheet_rows\b"),
            message="已移除 loader `sheetbook_sheet_rows`: 使用 `scalim.workflow.loaders:book_sheet_rows` / `^workflow/book_sheet_rows`.",
        ),
        _Rule(
            name="legacy-workbook-container-type",
            pattern=re.compile(r"container\.type:\s*workbook\b"),
            message="已移除 `.xlsx` 输出旧写法: 使用 `resources.books` + `outputs→book` 绑定.",
        ),
        _Rule(
            name="legacy-type-workbook",
            pattern=re.compile(r"(?<!container\.)\btype:\s*workbook\b"),
            message="已移除 `.xlsx` 输出旧写法: 使用 `resources.books` + `outputs→book` 绑定.",
        ),
        _Rule(
            name="legacy-writes-sheetbook-intent",
            pattern=re.compile(r"writes\[\*\]\.sheetbook_"),
            message="已移除 `sheetbook` 写入意图: 使用 `resources.books` + `outputs` 的 `write`.",
        ),
        _Rule(
            name="legacy-writes-sheetbook-intent-inline",
            pattern=re.compile(r"writes\.sheetbook_"),
            message="已移除 `sheetbook` 写入意图: 使用 `resources.books` + `outputs` 的 `write`.",
        ),
        _Rule(
            name="legacy-writes-workbook-intent-inline",
            pattern=re.compile(r"writes\.workbook_"),
            message="已移除 `workbook` 写入意图: 使用 `resources.books` + `outputs` 的 `write`.",
        ),
    )


def _scan_markdown(path: Path, *, rel_posix: str, rules: Iterable[_Rule]) -> List[Tuple[int, _Rule, str]]:
    text = _read_text(path)
    hits: List[Tuple[int, _Rule, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for rule in rules:
            if rule.pattern.search(line):
                hits.append((lineno, rule, line.rstrip("\n")))
    return hits


def main() -> int:
    root = _repo_root()
    rules = _rules()
    markdown_files = _git_ls_files(root, "*.md")

    errors: List[str] = []
    for rel_posix in markdown_files:
        if _is_allowed_markdown(rel_posix):
            continue
        path = (root / rel_posix).resolve()
        if not path.exists():
            continue
        hits = _scan_markdown(path, rel_posix=rel_posix, rules=rules)
        for lineno, rule, line in hits:
            errors.append("{}:{}: {}: {}\n  提示: {}".format(rel_posix, lineno, rule.name, line.strip(), rule.message))

    if errors:
        sys.stderr.write("`Markdown` SSOT 检查失败: 检测到遗留写法.\n")
        sys.stderr.write(
            "允许的例外: `agentdev/skills/.../references/upgrades/`, `yaml-dsl-upgrades.gen.md`, `llmanspec/changes/archive/`\n"
        )
        sys.stderr.write("违规项:\n")
        for item in errors[:200]:
            sys.stderr.write("- {}\n".format(item))
        if len(errors) > 200:
            sys.stderr.write("... 以及更多 {} 项.\n".format(len(errors) - 200))
        sys.stderr.write("\n修复: 更新相关文档/规范以匹配当前 SSOT.\n")
        return 1

    sys.stdout.write("OK: `Markdown` SSOT 检查通过.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
