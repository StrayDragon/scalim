# ruff: noqa: T201
"""
检查指定路径下的文档字符串与普通注释是否包含“未用反引号包裹”的英文描述.

设计目标:
- 注释/文档字符串的叙述部分使用中文.
- 代码标识符、库名、路径、配置键名等英文内容用反引号包裹,例如:`ConfigValidator`、`scalim.dsl.by_yaml`.
- 字段级说明字符串(“类字段语句”后紧跟的字符串表达式)也纳入检查范围.
- 结构标记与工具指令属于“机器可读注释”,保持不变,不纳入检查.

允许的英文(无需反引号):
- 全大写缩写白名单(例如:YAML、CSV、JSON 等)
- 需求编号:FR + 数字(例如:FR023)

用法:
    `python scripts/check-comments-cn.py`
    `python scripts/check-comments-cn.py src/scalim scripts notebooks`
"""

import argparse
import ast
import json
import re
import signal
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Set, Tuple


_REGION_RE = re.compile(r"^(region|endregion)\b", re.IGNORECASE)
_ASCII_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{1,}")
_FR_RE = re.compile(r"^FR\d+$")

_ALLOW_UPPER_TOKENS = frozenset(
    {
        "API",
        "CLI",
        "CPU",
        "CSV",
        "DSL",
        "ETL",
        "FIXME",
        "GPU",
        "HTTP",
        "HTTPS",
        "IR",
        "JSON",
        "NOTE",
        "PII",
        "SQL",
        "TODO",
        "URL",
        "UUID",
        "YAML",
    }
)

if hasattr(signal, "SIGPIPE"):
    try:
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    except Exception:
        pass


@dataclass(frozen=True)
class Violation:
    kind: str  # 违规类型:`comment` / `docstring` / `attr_docstring`
    path: str
    line: int
    tokens: Tuple[str, ...]


def _strip_backticks(text: str) -> str:
    # 轻量级处理:去掉 `...` 中的内容(包括反引号本身),避免把标识符当作“英文描述”.
    out: List[str] = []
    in_tick = False
    for ch in text:
        if ch == "`":
            in_tick = not in_tick
            continue
        if not in_tick:
            out.append(ch)
    return "".join(out)


def _is_tech_directive(comment_body: str) -> bool:
    lower = comment_body.strip().lower()
    if not lower:
        return True
    if lower.startswith("noinspection"):
        return True
    # 常见工具指令(保持原样)
    if "noqa" in lower:
        return True
    if "pyright:" in lower:
        return True
    if "pylint:" in lower:
        return True
    if "ruff:" in lower:
        return True
    if "fmt:" in lower:
        return True
    if "pragma:" in lower:
        return True
    if lower.startswith("type:"):
        return True
    return False


def _is_allowed_token(token: str) -> bool:
    if token.isupper() and token in _ALLOW_UPPER_TOKENS:
        return True
    if _FR_RE.match(token):
        return True
    return False


def _find_bad_ascii_tokens(text: str) -> Tuple[str, ...]:
    cleaned = _strip_backticks(text)
    bad: List[str] = []
    for m in _ASCII_TOKEN_RE.finditer(cleaned):
        tok = m.group(0)
        if _is_allowed_token(tok):
            continue
        bad.append(tok)
    return tuple(sorted(set(bad)))


def _is_excluded_path(path: Path) -> bool:
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
        ".tmp",
        # 第三方 `vendor` 代码:保留上游语言/格式
        "dataclassesx",
        "yamlx",
    }
    return any(part in excluded_dirs for part in path.parts)


def _iter_python_files(paths: Sequence[Path]) -> Iterator[Path]:
    seen: Set[Path] = set()
    for p in paths:
        if not p.exists():
            continue
        if p.is_file():
            if p.suffix == ".py" and not _is_excluded_path(p):
                resolved = p.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    yield resolved
            continue
        if p.is_dir():
            for path in sorted(p.rglob("*.py"), key=lambda x: str(x)):
                if _is_excluded_path(path):
                    continue
                resolved = path.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    yield resolved


def _iter_comment_violations(path: Path) -> Iterator[Violation]:
    try:
        with tokenize.open(str(path)) as f:
            for tok in tokenize.generate_tokens(f.readline):
                if tok.type != tokenize.COMMENT:
                    continue
                body = tok.string[1:].strip()
                if _REGION_RE.match(body):
                    continue
                if _is_tech_directive(body):
                    continue
                bad = _find_bad_ascii_tokens(body)
                if bad:
                    yield Violation(kind="comment", path=str(path), line=tok.start[0], tokens=bad)
    except OSError:
        return
    except tokenize.TokenError:
        return


def _is_docstring_expr(stmt: ast.stmt) -> bool:
    if not isinstance(stmt, ast.Expr):
        return False
    value = stmt.value
    if isinstance(value, ast.Str):  # Python 3.6
        return True
    if hasattr(ast, "Constant") and isinstance(value, ast.Constant) and isinstance(value.value, str):  # type: ignore[attr-defined]
        return True
    return False


def _get_docstring_and_line(node: Any) -> Tuple[Optional[str], Optional[int]]:
    # 返回 (`doc_expr`, `lineno`); 其中 `lineno` 为文档字符串表达式的起始行.
    body = getattr(node, "body", None)
    if not body:
        return None, None
    first = body[0]
    if not _is_docstring_expr(first):
        return None, None
    doc = ast.get_docstring(node, clean=False)
    line = getattr(first, "lineno", None)
    return doc, int(line or 0)


def _iter_docstring_violations(path: Path) -> Iterator[Violation]:
    try:
        src = tokenize.open(str(path)).read()
    except OSError:
        return

    try:
        mod = ast.parse(src, filename=str(path))
    except SyntaxError:
        return

    doc, line = _get_docstring_and_line(mod)
    if doc is not None and line is not None:
        bad = _find_bad_ascii_tokens(doc)
        if bad:
            yield Violation(kind="docstring", path=str(path), line=line, tokens=bad)

    for node in ast.walk(mod):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        doc, line = _get_docstring_and_line(node)
        if doc is None or line is None:
            continue
        bad = _find_bad_ascii_tokens(doc)
        if bad:
            yield Violation(kind="docstring", path=str(path), line=line, tokens=bad)


def _is_string_expr(stmt: ast.stmt) -> bool:
    if not isinstance(stmt, ast.Expr):
        return False
    value = stmt.value
    if isinstance(value, ast.Str):  # Python 3.6
        return True
    if hasattr(ast, "Constant") and isinstance(value, ast.Constant) and isinstance(value.value, str):  # type: ignore[attr-defined]
        return True
    return False


def _get_string_value(stmt: ast.stmt) -> Optional[str]:
    if not isinstance(stmt, ast.Expr):
        return None
    value = stmt.value
    if isinstance(value, ast.Str):  # Python 3.6
        return value.s
    if hasattr(ast, "Constant") and isinstance(value, ast.Constant) and isinstance(value.value, str):  # type: ignore[attr-defined]
        return value.value
    return None


def _iter_attribute_docstring_violations(path: Path) -> Iterator[Violation]:
    try:
        src = tokenize.open(str(path)).read()
    except OSError:
        return

    try:
        mod = ast.parse(src, filename=str(path))
    except SyntaxError:
        return

    for node in ast.walk(mod):
        if not isinstance(node, ast.ClassDef):
            continue
        body = node.body
        if not body:
            continue
        i = 0
        while i < len(body) - 1:
            cur = body[i]
            nxt = body[i + 1]

            is_field_stmt = False
            if isinstance(cur, ast.AnnAssign) and isinstance(cur.target, ast.Name):
                is_field_stmt = True
            elif isinstance(cur, ast.Assign) and len(cur.targets) == 1 and isinstance(cur.targets[0], ast.Name):
                is_field_stmt = True

            if not is_field_stmt or not _is_string_expr(nxt):
                i += 1
                continue

            text = _get_string_value(nxt) or ""
            bad = _find_bad_ascii_tokens(text)
            if bad:
                line = getattr(nxt, "lineno", 0) or 0
                yield Violation(kind="attr_docstring", path=str(path), line=int(line), tokens=bad)

            i += 2


def scan_paths(paths: Sequence[Path]) -> List[Violation]:
    violations: List[Violation] = []
    for path in _iter_python_files(paths):
        violations.extend(list(_iter_comment_violations(path)))
        violations.extend(list(_iter_docstring_violations(path)))
        violations.extend(list(_iter_attribute_docstring_violations(path)))
    return violations


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="检查注释与文档字符串是否包含未包裹的英文描述.")
    p.add_argument("paths", nargs="*", help="要扫描的路径(文件或目录). 默认: `src/scalim/`")
    p.add_argument("--json", action="store_true", help="输出 JSON.")
    p.add_argument("--show-tokens", action="store_true", help="在文本输出中显示命中的英文 token 列表.")
    return p.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    repo_root = Path(__file__).resolve().parent.parent
    if args.paths:
        scan_inputs = [Path(p) for p in args.paths]
        scan_paths_list = [(p if p.is_absolute() else (repo_root / p)).resolve() for p in scan_inputs]
    else:
        scan_paths_list = [(repo_root / "src" / "scalim").resolve()]

    violations = scan_paths(scan_paths_list)
    if args.json:
        payload: List[Dict[str, Any]] = [{"kind": v.kind, "path": v.path, "line": v.line, "tokens": list(v.tokens)} for v in violations]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if not violations:
            print("未发现违规项.")
            return 0

        print("发现未用反引号包裹的英文描述/标识符:")
        for v in violations:
            if args.show_tokens:
                extra = " tokens={}".format(", ".join(v.tokens))
            else:
                extra = ""
            try:
                rel = str(Path(v.path).resolve().relative_to(repo_root))
            except Exception:
                rel = v.path
            print("- {}:{}:{}{}".format(rel, v.line, v.kind, extra))

        print("")
        print("总计:{} 条.".format(len(violations)))
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
