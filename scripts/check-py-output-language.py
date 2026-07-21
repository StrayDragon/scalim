# ruff: noqa: T201
# force-en
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
    `python scripts/check-py-output-language.py --report .tmp/artifacts/output-language.report.txt --quiet`

退出码:
- 0: 未发现命中
- 1: 发现命中

输出合约:
- `--quiet` 且无命中时不写 `stdout`/`stderr`; 有命中时仍写(命中走 `stderr`).
- `--report` 始终落盘(含“未发现命中.”),与 `--quiet` 正交.
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

_DEFAULT_ALLOW_FILE_REL = Path("scripts") / "check-py-output-language.allow.txt"


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


def _load_allow_file(path: Path) -> Tuple[Set[str], List[str]]:
    """加载允许名单文件,返回(允许路径集合, 错误列表).

    文件不存在时返回空集合(无错误),便于测试场景和首次使用.
    """
    if not path.exists():
        return set(), []

    errors: List[str] = []
    allowed: Set[str] = set()
    for idx, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("- "):
            errors.append("{}:{}: 不应以 '- ' 开头(只需写相对路径): {!r}".format(str(path), idx, raw))
            continue
        allowed.add(line)
    return allowed, errors


def _is_path_allowed(rel: str, allowed: Set[str]) -> bool:
    # force-en
    """rel 是否匹配允许名单中的任一条目(前缀匹配,支持目录级放行)."""
    return any(rel.startswith(entry) for entry in allowed)


def _write_allow_file(path: Path, rel_paths: Sequence[str]) -> None:
    # force-en
    lines = [
        "# Generated by `scripts/check-py-output-language.py --update-allow-file`.",
        "# One entry per line (文件路径或目录前缀,目录会匹配其下所有文件).",
        "",
    ]
    lines.extend(list(rel_paths))
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="扫描 print/logger/raise 等输出点中的英文描述.")
    p.add_argument("--include-tests", action="store_true", help="包含 tests/ (默认不包含).")
    p.add_argument("--min-word-len", type=int, default=3, help="英文单词最小长度(默认: 3).")
    p.add_argument(
        "--report",
        default="",
        help="将完整报告写入文件(例如: .tmp/artifacts/output-language.report.txt). 若为空则仅输出到 stderr.",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="静默模式: 无命中时不写 stdout/stderr; 不影响 --report 落盘.",
    )
    p.add_argument(
        "--allow-file",
        default=str(_DEFAULT_ALLOW_FILE_REL),
        help="允许名单文件路径(默认: scripts/check-py-output-language.allow.txt).",
    )
    p.add_argument("--strict", action="store_true", help="严格模式: 不使用允许名单; 发现任意命中即失败.")
    p.add_argument("--update-allow-file", action="store_true", help="更新允许名单文件为当前命中集合(便于增量治理).")
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

    # 计算命中文件集合(按文件去重,用于允许名单)
    hit_paths: dict[str, Path] = {}
    for h in hits:
        rel = str(h.path.relative_to(repo_root))
        if rel not in hit_paths:
            hit_paths[rel] = h.path
    sorted_hit_paths = sorted(hit_paths.keys())

    allow_file = (repo_root / str(args.allow_file)).resolve()

    if args.update_allow_file:
        _write_allow_file(allow_file, sorted_hit_paths)
        print("[更新] 已写入允许名单 ({} 条): {}".format(len(sorted_hit_paths), str(allow_file.relative_to(repo_root))))
        return 0

    # 加载允许名单
    allowed: Set[str] = set()
    if not args.strict:
        allowed, allow_errors = _load_allow_file(allow_file)
        if allow_errors:
            print("[错误] 允许名单解析失败:", file=sys.stderr)
            for line in allow_errors:
                print("- {}".format(line), file=sys.stderr)
            return 2

    # 过滤:只报告不在允许名单中的文件(前缀匹配,支持目录)
    if not args.strict and allowed:
        unexpected_hits = [h for h in hits if not _is_path_allowed(str(h.path.relative_to(repo_root)), allowed)]
    else:
        unexpected_hits = hits

    out_lines: List[str] = []
    if unexpected_hits:
        out_lines.append("检测到运行时输出文案中的英文(建议改为中文或用反引号包裹;必要时可用 `# force-en` 跳过):")
        for h in unexpected_hits:
            rel = h.path.relative_to(repo_root)
            out_lines.append(f"{rel}:{h.line}:{h.col}  [{h.kind}]  {h.sample}")
        out_lines.append("")
        out_lines.append("总计:{} 处".format(len(unexpected_hits)))
        if not args.strict:
            out_lines.append("更新允许名单: 运行 `uv run scripts/check-py-output-language.py --update-allow-file`")
    else:
        # 通过:报告存量信息
        if hit_paths and not args.strict:
            stale = sorted(entry for entry in allowed if not any(rel.startswith(entry) for rel in sorted_hit_paths))
            summary = "[通过] 未新增英文输出文案 (历史存量 {} 个文件仍在允许名单).".format(len(hit_paths))
            if stale:
                summary += " (允许名单可收敛: {} 条已不再命中)".format(len(stale))
            out_lines.append(summary)
        else:
            out_lines.append("未发现命中.")

    output = "\n".join(out_lines) + "\n"
    if args.report:
        report_path = (repo_root / str(args.report)).resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(output, encoding="utf-8")

    if not args.quiet or unexpected_hits:
        stream = sys.stderr if unexpected_hits else sys.stdout
        stream.write(output)
    return 1 if unexpected_hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
