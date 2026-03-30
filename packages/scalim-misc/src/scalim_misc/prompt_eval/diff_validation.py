from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Sequence, Tuple

if TYPE_CHECKING:
    from pathlib import Path

_AUTOGEN_BEGIN_RE = re.compile(r"<!--\s*BEGIN AUTOGEN:([A-Za-z0-9_.-]+)\s*-->")
_AUTOGEN_END_RE = re.compile(r"<!--\s*END AUTOGEN:([A-Za-z0-9_.-]+)\s*-->")

_DIFF_FILE_RE = re.compile(r"^diff --git a/(.+) b/(.+)$")
_DIFF_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


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


def parse_patch(text: str) -> Tuple[FilePatch, ...]:
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
    # 区间为闭区间(行号为 `1-based`).
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


def validate_generated_file_boundary(file_patches: Sequence[FilePatch], *, allow_gen: bool) -> List[Issue]:
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


def validate_injected_block_boundary(file_patches: Sequence[FilePatch], *, root: Path) -> List[Issue]:  # noqa: C901
    issues: List[Issue] = []
    for fp in file_patches:
        base_path = _effective_existing_path(root, fp)
        if base_path is None:
            continue
        ranges = _autogen_block_ranges(read_text(base_path))
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


def validate_patch_text(patch_text: str, *, root: Path, allow_gen: bool) -> List[Issue]:
    file_patches = parse_patch(patch_text)
    if not file_patches:
        return [
            Issue(
                code="patch_parse",
                message="无法解析补丁(缺少 `diff --git a/... b/...` 头).",
            )
        ]

    issues: List[Issue] = []
    issues.extend(validate_generated_file_boundary(file_patches, allow_gen=allow_gen))
    issues.extend(validate_injected_block_boundary(file_patches, root=root))
    return issues
