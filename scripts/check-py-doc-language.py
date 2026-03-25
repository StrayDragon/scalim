from __future__ import annotations

import ast
import io
import re
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path


_WORD_RE = re.compile(r"\b[A-Za-z]{3,}\b")
_URL_RE = re.compile(r"https?://\S+")
_BACKTICK_RE = re.compile(r"`[^`]*`")
_FENCED_CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)

_ALLOWED_WORDS_LOWER = {
    "api",
    "ci",
    "cpu",
    "csv",
    "dsl",
    "gpu",
    "http",
    "https",
    "ide",
    "ir",
    "json",
    "mkdocs",
    "pandas",
    "python",
    "ruff",
    "scalim",
    "scalim_lite",
    "lite",
    "sql",
    "ssl",
    "tcp",
    "tls",
    "udp",
    "url",
    "uuid",
    "utc",
    # `Google` 风格文档字符串的段落标题视为固定例外.
    "args",
    "arguments",
    "attributes",
    "example",
    "examples",
    "note",
    "notes",
    "raises",
    "return",
    "returns",
    "yield",
    "yields",
}

_DEFAULT_REL_ROOTS = (
    Path("src") / "scalim",
    Path("scripts"),
    Path("notebooks"),
)

_GOOGLE_STYLE_SECTION_HEADERS = frozenset(
    {
        "Args",
        "Arguments",
        "Attributes",
        "Returns",
        "Return",
        "Raises",
        "Yields",
        "Yield",
        "Examples",
        "Example",
        "Notes",
        "Note",
    }
)
_GOOGLE_STYLE_PARAM_SECTIONS = frozenset({"Args", "Arguments", "Attributes"})
_GOOGLE_STYLE_RETURNS_SECTIONS = frozenset({"Returns", "Return", "Yields", "Yield"})

_GOOGLE_STYLE_SECTION_HEADER_RE = re.compile(
    r"^(\s*)(" + "|".join(sorted(_GOOGLE_STYLE_SECTION_HEADERS, key=len, reverse=True)) + r")\s*:\s*$"
)
_GOOGLE_STYLE_PARAM_LINE_RE = re.compile(r"^(\s*)(\*{0,2}[A-Za-z_][A-Za-z0-9_]*)(?:\s*\([^)]*\))?(\s*:\s*)(.*?)(\r?\n)?$")
_GOOGLE_STYLE_TUPLE_IDENTIFIER_LIST_RE = re.compile(r"\(\s*(?:\*{0,2}[A-Za-z_][A-Za-z0-9_]*\s*,\s*)+(?:\*{0,2}[A-Za-z_][A-Za-z0-9_]*)\s*\)")
_GOOGLE_STYLE_BARE_IDENTIFIER_LIST_RE = re.compile(r"^(?:\*{0,2}[A-Za-z_][A-Za-z0-9_]*\s*,\s*)+(?:\*{0,2}[A-Za-z_][A-Za-z0-9_]*)$")
_FORCE_EN_MARK = "force-en"


@dataclass(frozen=True)
class _Hit:
    path: Path
    line: int
    col: int
    kind: str
    sample: str


def _iter_python_files(*, repo_root: Path, rel_roots: tuple[Path, ...]) -> list[Path]:
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
        "tests",
        # 第三方 `vendor` 代码:保留上游语言/格式
        "dataclassesx",
    }

    py_files: list[Path] = []
    for rel_root in rel_roots:
        root = repo_root / rel_root
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


def _strip_google_style_param_names(text: str) -> str:
    """移除 `Google` 风格文档字符串中的标识符,避免误报(例如 `Args:` 下的 `config:`)."""
    out_lines: list[str] = []
    current_section: str = ""
    header_indent: int = -1

    for line in text.splitlines(True):
        m_header = _GOOGLE_STYLE_SECTION_HEADER_RE.match(line)
        if m_header:
            current_section = m_header.group(2)
            header_indent = len(m_header.group(1))
            out_lines.append(line)
            continue

        if current_section in _GOOGLE_STYLE_PARAM_SECTIONS:
            if not line.strip():
                out_lines.append(line)
                continue

            leading = len(line) - len(line.lstrip(" "))
            if leading <= header_indent:
                current_section = ""
                header_indent = -1
                out_lines.append(line)
                continue

            m_param = _GOOGLE_STYLE_PARAM_LINE_RE.match(line)
            if m_param:
                line = m_param.group(1) + m_param.group(3) + m_param.group(4) + (m_param.group(5) or "")

        if current_section in _GOOGLE_STYLE_RETURNS_SECTIONS:
            if not line.strip():
                out_lines.append(line)
                continue

            leading = len(line) - len(line.lstrip(" "))
            if leading <= header_indent:
                current_section = ""
                header_indent = -1
                out_lines.append(line)
                continue

            line_ending = ""
            if line.endswith("\r\n"):
                line_ending = "\r\n"
                core = line[:-2]
            elif line.endswith("\n"):
                line_ending = "\n"
                core = line[:-1]
            else:
                core = line

            stripped_core = core.strip()
            if _GOOGLE_STYLE_BARE_IDENTIFIER_LIST_RE.match(stripped_core) or _GOOGLE_STYLE_TUPLE_IDENTIFIER_LIST_RE.fullmatch(
                stripped_core
            ):
                indent = core[: len(core) - len(core.lstrip(" "))]
                line = indent + line_ending
            else:
                line = _GOOGLE_STYLE_TUPLE_IDENTIFIER_LIST_RE.sub("", core) + line_ending

        out_lines.append(line)

    return "".join(out_lines)


def _is_probably_identifier(word: str) -> bool:
    if word.lower() in _ALLOWED_WORDS_LOWER:
        return True
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


def _find_english_words(text: str) -> list[str]:
    cleaned = _strip_ignored_segments(text)
    cleaned = _strip_google_style_param_names(cleaned)
    words = _WORD_RE.findall(cleaned)
    return [w for w in words if not _is_probably_identifier(w)]


def _has_ignore_mark(stripped_comment: str) -> bool:
    return _FORCE_EN_MARK in stripped_comment.lower()


def _is_directive_comment(comment: str) -> bool:
    if comment.startswith("#!"):
        return True
    stripped = comment.lstrip("#").strip()
    if not stripped:
        return True
    if _has_ignore_mark(stripped):
        return True
    if stripped.startswith(("region", "endregion")):
        return True
    if "noqa" in stripped:
        return True
    if stripped.startswith(("type:", "pyright:", "pragma:", "ruff:", "fmt:", "isort:", "pylint:")):
        return True
    if stripped.startswith("-*-") or stripped.startswith("coding:"):
        return True
    return False


def _iter_docstring_expr_nodes(tree: ast.AST) -> dict[int, ast.Expr]:
    doc_nodes: dict[int, ast.Expr] = {}

    def maybe_add_doc_expr(body: list[ast.stmt]) -> None:
        if not body:
            return
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            doc_nodes[id(first)] = first

    if isinstance(tree, ast.Module):
        maybe_add_doc_expr(tree.body)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            maybe_add_doc_expr(node.body)

    return doc_nodes


def _iter_docstrings(tree: ast.AST) -> list[tuple[int, int, str, str]]:
    items: list[tuple[int, int, str, str]] = []
    doc_nodes = _iter_docstring_expr_nodes(tree)

    for expr in doc_nodes.values():
        const = expr.value
        assert isinstance(const, ast.Constant) and isinstance(const.value, str)
        items.append((expr.lineno, expr.col_offset, "docstring", const.value))

    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and id(node) not in doc_nodes:
            const = node.value
            if isinstance(const, ast.Constant) and isinstance(const.value, str):
                items.append((node.lineno, node.col_offset, "string-expr", const.value))

    return items


def _iter_comments(src: str) -> list[tuple[int, int, str]]:
    comments: list[tuple[int, int, str]] = []
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
        comments.append((tok.start[0], tok.start[1], tok.string))
    return comments


def _iter_ignore_comment_lines(src: str) -> set[int]:
    ignore_lines: set[int] = set()
    for line, _col, comment in _iter_comments(src):
        stripped = comment.lstrip("#").strip()
        if _has_ignore_mark(stripped):
            ignore_lines.add(line)
    return ignore_lines


def _is_ignored_by_comment(ignore_lines: set[int], *, line: int, end_line: Optional[int] = None) -> bool:
    if line <= 0:
        return False
    if line in ignore_lines or line - 1 in ignore_lines:
        return True
    if end_line is None or end_line <= line:
        return False
    for current in range(line + 1, end_line + 1):
        if current in ignore_lines:
            return True
    return False


def _summarize_sample(text: str) -> str:
    one_line = " ".join(text.strip().splitlines()).strip()
    if len(one_line) > 120:  # noqa: PLR2004
        return one_line[:117] + "..."
    return one_line


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    hits: list[_Hit] = []

    for path in _iter_python_files(repo_root=repo_root, rel_roots=_DEFAULT_REL_ROOTS):
        try:
            src = path.read_text(encoding="utf-8")
        except Exception:
            continue

        try:
            tree = ast.parse(src, filename=str(path))
        except SyntaxError:
            continue

        ignore_lines = _iter_ignore_comment_lines(src)

        for line, col, kind, doc in _iter_docstrings(tree):
            if _is_ignored_by_comment(
                ignore_lines,
                line=line,
                end_line=None,
            ):
                continue
            words = _find_english_words(doc)
            if not words:
                continue
            hits.append(_Hit(path=path, line=line, col=col, kind=kind, sample=_summarize_sample(doc)))

        for line, col, comment in _iter_comments(src):
            if _is_ignored_by_comment(ignore_lines, line=line):
                continue
            if _is_directive_comment(comment):
                continue
            words = _find_english_words(comment)
            if not words:
                continue
            hits.append(_Hit(path=path, line=line, col=col, kind="comment", sample=_summarize_sample(comment)))

    if not hits:
        return 0

    print(
        "检测到英文注释/文档字符串(请改为中文,或将代码/术语放入反引号 `...` 中;必要时可用 `# force-en` 显式跳过):",
        file=sys.stderr,
    )
    for hit in hits:
        rel = hit.path.relative_to(repo_root)
        print(f"{rel}:{hit.line}:{hit.col}  [{hit.kind}]  {hit.sample}", file=sys.stderr)
    print(f"\n总计:{len(hits)} 处", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
