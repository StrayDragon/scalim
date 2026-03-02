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
    "sql",
    "ssl",
    "tcp",
    "tls",
    "udp",
    "url",
    "uuid",
    "utc",
}


@dataclass(frozen=True)
class _Hit:
    path: Path
    line: int
    col: int
    kind: str
    sample: str


def _iter_python_files(repo_root: Path) -> list[Path]:
    excluded_dirs = {
        ".git",
        ".venv",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        "site",
        "tests",
    }

    excluded_prefixes = {
        repo_root / "src" / "scalim" / "vendor",
    }

    py_files: list[Path] = []
    for path in repo_root.rglob("*.py"):
        if any(part in excluded_dirs for part in path.parts):
            continue
        if any(path.is_relative_to(prefix) for prefix in excluded_prefixes):
            continue
        py_files.append(path)
    return sorted(py_files)


def _strip_ignored_segments(text: str) -> str:
    text = _URL_RE.sub("", text)
    text = _FENCED_CODE_BLOCK_RE.sub("", text)
    text = _BACKTICK_RE.sub("", text)
    return text


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
    words = _WORD_RE.findall(cleaned)
    return [w for w in words if not _is_probably_identifier(w)]


def _is_directive_comment(comment: str) -> bool:
    if comment.startswith("#!"):
        return True
    stripped = comment.lstrip("#").strip()
    if not stripped:
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
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type != tokenize.COMMENT:
            continue
        comments.append((tok.start[0], tok.start[1], tok.string))
    return comments


def _summarize_sample(text: str) -> str:
    one_line = " ".join(text.strip().splitlines()).strip()
    if len(one_line) > 120:  # noqa: PLR2004
        return one_line[:117] + "..."
    return one_line


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    hits: list[_Hit] = []

    for path in _iter_python_files(repo_root):
        try:
            src = path.read_text(encoding="utf-8")
        except Exception:
            continue

        try:
            tree = ast.parse(src, filename=str(path))
        except SyntaxError:
            continue

        for line, col, kind, doc in _iter_docstrings(tree):
            words = _find_english_words(doc)
            if not words:
                continue
            hits.append(_Hit(path=path, line=line, col=col, kind=kind, sample=_summarize_sample(doc)))

        for line, col, comment in _iter_comments(src):
            if _is_directive_comment(comment):
                continue
            words = _find_english_words(comment)
            if not words:
                continue
            hits.append(_Hit(path=path, line=line, col=col, kind="comment", sample=_summarize_sample(comment)))

    if not hits:
        return 0

    print("检测到英文注释/Docstring(请改为中文,或将代码/术语放入反引号 `...` 中):", file=sys.stderr)
    for hit in hits:
        rel = hit.path.relative_to(repo_root)
        print(f"{rel}:{hit.line}:{hit.col}  [{hit.kind}]  {hit.sample}", file=sys.stderr)
    print(f"\n总计:{len(hits)} 处", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
