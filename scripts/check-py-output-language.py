# ruff: noqa: T201
"""
扫描运行时“文字输出点”中的英文描述(例如: `print`/`logger`/`raise`).

目标:
- 运行时面向用户的文案应以中文为主.
- 代码标识符/路径/协议名等英文内容建议用反引号包裹,例如:`case_id`、`HTTP`、`src/scalim/...`.
- 如确需保留英文,可在语句覆盖行添加 `# force-en` 跳过该命中点.

当前扫描点(仅 Python):
- `print(...)`
- `logging.<level>(...)` / `<logger>.<level>(...)` (`debug`/`info`/`warning`/`error`/`exception`/`critical`/`fatal`/`log`)
- `warnings.warn(...)`
- `sys.stdout.write(...)` / `sys.stderr.write(...)`
- `raise SomeError("...")`
- `assert cond, "..."` (断言消息)

用法:
    `python scripts/check-py-output-language.py`
    `python scripts/check-py-output-language.py --report .tmp/artifacts/output-language.report.txt`

退出码:
- 0: 未发现命中
- 1: 发现命中
"""

from __future__ import annotations

import argparse
import ast
import io
import re
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Sequence, Set, Tuple


_FORCE_EN_MARK = "force-en"

_URL_RE = re.compile(r"https?://\S+")
_BACKTICK_RE = re.compile(r"`[^`]*`")
_FENCED_CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)


def _word_re(*, min_word_len: int) -> re.Pattern[str]:
    return re.compile(r"\b[A-Za-z]{" + str(int(min_word_len)) + r",}\b")


_LOGGER_LEVEL_ATTRS = frozenset({"debug", "info", "warning", "warn", "error", "exception", "critical", "fatal", "log"})


_DEFAULT_REL_ROOTS = (
    Path("src") / "scalim",
    Path("scripts"),
    Path("notebooks"),
    Path("packages"),
)


@dataclass(frozen=True)
class _Hit:
    path: Path
    line: int
    col: int
    kind: str
    sample: str


def _iter_python_files(*, repo_root: Path, rel_roots: tuple[Path, ...], include_tests: bool) -> list[Path]:
    excluded_dirs = {
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
        # 第三方 `vendor` 代码:保留上游语言/格式
        "dataclassesx",
        "yamlx",
    }
    if not include_tests:
        excluded_dirs.add("tests")

    py_files: list[Path] = []
    for rel_root in rel_roots:
        root = (repo_root / rel_root).resolve()
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            try:
                rel = path.relative_to(repo_root)
            except Exception:
                continue
            if any(part in excluded_dirs for part in rel.parts):
                continue
            py_files.append(path)

    return sorted(set(py_files))


def _strip_ignored_segments(text: str) -> str:
    text = _URL_RE.sub("", text)
    text = _FENCED_CODE_BLOCK_RE.sub("", text)
    text = _BACKTICK_RE.sub("", text)
    return text


def _is_probably_identifier(word: str) -> bool:
    if word in {"None", "True", "False"}:
        return True
    if "_" in word:
        return True
    if any(ch.isdigit() for ch in word):
        return True
    if re.search(r"[a-z][A-Z]", word):
        return True
    if re.search(r"[A-Z][a-z]+[A-Z]", word):
        return True
    if word.isupper() and len(word) <= 6:  # noqa: PLR2004
        return True
    return False


def _find_english_words(text: str, *, min_word_len: int) -> Tuple[str, ...]:
    cleaned = _strip_ignored_segments(text)
    words = _word_re(min_word_len=min_word_len).findall(cleaned)
    return tuple(sorted({w for w in words if not _is_probably_identifier(w)}))


def _summarize(text: str) -> str:
    one_line = " ".join(text.strip().splitlines()).strip()
    if len(one_line) > 160:  # noqa: PLR2004
        return one_line[:157] + "..."
    return one_line


def _iter_force_en_comment_lines(src: str) -> Set[int]:
    force_lines: Set[int] = set()
    in_uv_script_metadata = False
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type != tokenize.COMMENT:
            continue
        stripped = tok.string.lstrip("#").strip()
        if stripped == "/// script":
            in_uv_script_metadata = True
            continue
        if in_uv_script_metadata:
            if stripped == "///":
                in_uv_script_metadata = False
            continue
        if _FORCE_EN_MARK in stripped:
            force_lines.add(int(tok.start[0]))
    return force_lines


def _node_span_lines(node: ast.AST) -> Tuple[int, int]:
    start = int(getattr(node, "lineno", 0) or 0)
    end = int(getattr(node, "end_lineno", 0) or 0)
    if end <= 0:
        end = start
    return start, end


def _has_force_en(force_lines: Set[int], node: ast.AST) -> bool:
    start, end = _node_span_lines(node)
    if start <= 0:
        return False
    for ln in range(start, end + 1):
        if ln in force_lines:
            return True
    return False


def _extract_text(expr: ast.AST) -> Optional[str]:
    # 仅提取静态字符串部分;对 `f-string` 仅保留常量片段.
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return expr.value
    if isinstance(expr, ast.JoinedStr):
        parts: List[str] = []
        for v in expr.values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                parts.append(v.value)
        return "".join(parts)
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Add):
        left = _extract_text(expr.left)
        right = _extract_text(expr.right)
        if left is None and right is None:
            return None
        return (left or "") + (right or "")
    if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute) and expr.func.attr == "format":
        base = _extract_text(expr.func.value)
        return base
    return None


def _iter_message_exprs_for_call(call: ast.Call) -> Iterator[Tuple[str, ast.AST]]:
    func = call.func
    if isinstance(func, ast.Name) and func.id == "print":
        for arg in call.args:
            text = _extract_text(arg)
            if text:
                yield text, arg
        return

    if isinstance(func, ast.Attribute):
        attr = func.attr
        if isinstance(func.value, ast.Attribute) and isinstance(func.value.value, ast.Name) and func.value.value.id == "sys":
            if func.value.attr in {"stdout", "stderr"} and attr == "write" and call.args:
                text = _extract_text(call.args[0])
                if text:
                    yield text, call.args[0]
                return

        if isinstance(func.value, ast.Name) and func.value.id == "warnings" and attr == "warn" and call.args:
            text = _extract_text(call.args[0])
            if text:
                yield text, call.args[0]
            return

        if attr in _LOGGER_LEVEL_ATTRS:
            if attr == "log":
                if len(call.args) >= 2:  # `logger.log(level, msg, *args)`
                    text = _extract_text(call.args[1])
                    if text:
                        yield text, call.args[1]
                return
            if call.args:
                text = _extract_text(call.args[0])
                if text:
                    yield text, call.args[0]
            return


def _iter_output_string_hits(*, path: Path, src: str, tree: ast.AST, min_word_len: int) -> Iterator[_Hit]:
    force_lines = _iter_force_en_comment_lines(src)
    src_lines = src.splitlines()

    def context_line(line_no: int) -> str:
        if line_no <= 0 or line_no > len(src_lines):
            return ""
        return src_lines[line_no - 1].rstrip("\n")

    for node in ast.walk(tree):
        # 1) 断言消息
        if isinstance(node, ast.Assert) and node.msg is not None:
            if _has_force_en(force_lines, node):
                continue
            text = _extract_text(node.msg)
            if not text:
                continue
            words = _find_english_words(text, min_word_len=min_word_len)
            if not words:
                continue
            ln = int(getattr(node.msg, "lineno", getattr(node, "lineno", 0)) or 0)
            col = int(getattr(node.msg, "col_offset", getattr(node, "col_offset", 0)) or 0)
            yield _Hit(path=path, line=ln, col=col, kind="assert", sample=_summarize(context_line(ln)))
            continue

        # 2) `raise Exception("msg")`
        if isinstance(node, ast.Raise) and node.exc is not None:
            if _has_force_en(force_lines, node):
                continue
            exc = node.exc
            if isinstance(exc, ast.Call):
                # 优先看位置参数第一个
                if exc.args:
                    msg_expr = exc.args[0]
                    text = _extract_text(msg_expr)
                    if text:
                        words = _find_english_words(text, min_word_len=min_word_len)
                        if words:
                            ln = int(getattr(msg_expr, "lineno", getattr(node, "lineno", 0)) or 0)
                            col = int(getattr(msg_expr, "col_offset", getattr(node, "col_offset", 0)) or 0)
                            yield _Hit(path=path, line=ln, col=col, kind="raise", sample=_summarize(context_line(ln)))
                continue

        # 3) `print`/`logger`/`warnings.warn`/`sys.*.write`
        if isinstance(node, ast.Call):
            if _has_force_en(force_lines, node):
                continue

            for text, text_node in _iter_message_exprs_for_call(node):
                words = _find_english_words(text, min_word_len=min_word_len)
                if not words:
                    continue
                ln = int(getattr(text_node, "lineno", getattr(node, "lineno", 0)) or 0)
                col = int(getattr(text_node, "col_offset", getattr(node, "col_offset", 0)) or 0)

                kind = "call"
                func = node.func
                if isinstance(func, ast.Name) and func.id == "print":
                    kind = "print"
                elif isinstance(func, ast.Attribute):
                    if func.attr == "write":
                        kind = "write"
                    elif func.attr == "warn" and isinstance(func.value, ast.Name) and func.value.id == "warnings":
                        kind = "warnings"
                    elif func.attr in _LOGGER_LEVEL_ATTRS:
                        kind = "logger"

                yield _Hit(path=path, line=ln, col=col, kind=kind, sample=_summarize(context_line(ln)))


def scan_repo(
    *,
    repo_root: Path,
    rel_roots: tuple[Path, ...],
    include_tests: bool,
    min_word_len: int,
) -> list[_Hit]:
    hits: list[_Hit] = []
    for path in _iter_python_files(repo_root=repo_root, rel_roots=rel_roots, include_tests=include_tests):
        try:
            src = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            src = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        try:
            tree = ast.parse(src, filename=str(path))
        except SyntaxError:
            continue

        hits.extend(list(_iter_output_string_hits(path=path, src=src, tree=tree, min_word_len=min_word_len)))

    return sorted(hits, key=lambda h: (str(h.path), h.line, h.col, h.kind))


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="扫描 print/logger/raise 等输出点中的英文描述.")
    p.add_argument("--include-tests", action="store_true", help="包含 tests/ (默认不包含).")
    p.add_argument("--min-word-len", type=int, default=3, help="英文单词最小长度(默认: 3).")
    p.add_argument(
        "--report",
        default="",
        help="将完整报告写入文件(例如: .tmp/artifacts/output-language.report.txt). 若为空则仅输出到 stderr.",
    )
    return p.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]

    hits = scan_repo(
        repo_root=repo_root,
        rel_roots=_DEFAULT_REL_ROOTS,
        include_tests=bool(args.include_tests),
        min_word_len=int(args.min_word_len),
    )

    out_lines: List[str] = []
    if hits:
        out_lines.append("检测到运行时输出文案中的英文(建议改为中文或用反引号包裹;必要时可用 `# force-en` 跳过):")
        for h in hits:
            rel = h.path.relative_to(repo_root)
            out_lines.append(f"{rel}:{h.line}:{h.col}  [{h.kind}]  {h.sample}")
        out_lines.append("")
        out_lines.append("总计:{} 处".format(len(hits)))
    else:
        out_lines.append("未发现命中.")

    output = "\n".join(out_lines) + "\n"
    if args.report:
        report_path = (repo_root / str(args.report)).resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(output, encoding="utf-8")

    stream = sys.stderr if hits else sys.stdout
    stream.write(output)
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
