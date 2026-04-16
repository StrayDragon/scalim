#!/usr/bin/env python3
"""公共接口治理工具链的共享辅助函数.

`SSOT`:
  - 第 1 层（`tier1`）入口：
      `src/scalim/**/__init__.py` 中的标记:
      `# pragma: scalim-public-api tier1:<order>:<module>|<desc>|<scenario>`
  - 符号级导出：各模块的字面量 `__all__`（字符串常量组成的 `tuple`/`list`）。

约束:
  - 仅 `AST` 扫描：不 `import` 项目模块（避免副作用与可选依赖导致的不稳定）。
  - 输出确定性：排序规则显式且稳定。
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class PublicApiEntrypointMarker:
    tier: int
    order: int
    module: str
    description: str
    common_scenario: str
    marker_path: Path
    marker_lineno: int


@dataclass(frozen=True)
class PublicApiProblem:
    path: Path
    lineno: int
    module: str
    reason: str


@dataclass(frozen=True)
class ModuleAllLiteral:
    values: Tuple[str, ...]
    kind: str
    lineno: int


_ENTRYPOINT_MARKER_RE = re.compile(
    r"^#\s*pragma:\s*scalim-public-api\s+tier(?P<tier>\d+):(?P<order>\d+):(?P<module>[A-Za-z0-9_\\.]+)\|(?P<desc>[^|]*)\|(?P<scenario>.*)$",
    flags=re.IGNORECASE,
)


def repo_root_for_script(script_path: Path) -> Path:
    return script_path.resolve().parents[1]


def is_relative_to(path: Path, maybe_parent: Path) -> bool:
    try:
        path.relative_to(maybe_parent)
    except ValueError:
        return False
    return True


def iter_py_files(root: Path, *, exclude_dirs: Sequence[Path]) -> Iterable[Path]:
    for path in sorted(root.rglob("*.py"), key=lambda p: str(p)):
        if not path.is_file():
            continue
        if any(is_relative_to(path, ex) for ex in exclude_dirs):
            continue
        yield path


def iter_tier1_marker_files(repo_root: Path) -> Iterable[Path]:
    scan_root = repo_root / "src" / "scalim"
    exclude_dirs = (scan_root / "vendor",)
    for path in sorted(scan_root.rglob("__init__.py"), key=lambda p: str(p)):
        if not path.is_file():
            continue
        if any(is_relative_to(path, ex) for ex in exclude_dirs):
            continue
        yield path


def discover_public_api_entrypoints(
    repo_root: Path, *, tier: int
) -> Tuple[Tuple[PublicApiEntrypointMarker, ...], Tuple[PublicApiProblem, ...]]:
    """从 `__init__.py` 标记中发现“编目的入口模块”.

    返回：`(entrypoints, problems)`。
    """

    entrypoints: List[PublicApiEntrypointMarker] = []
    problems: List[PublicApiProblem] = []

    for path in iter_tier1_marker_files(repo_root):
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            m = _ENTRYPOINT_MARKER_RE.match(line.strip())
            if not m:
                continue
            got_tier = int(m.group("tier"))
            if got_tier != int(tier):
                continue

            module = str(m.group("module") or "").strip()
            desc = str(m.group("desc") or "").strip()
            scenario = str(m.group("scenario") or "").strip()
            order = int(m.group("order"))

            if not module:
                problems.append(PublicApiProblem(path=path, lineno=lineno, module="", reason="tier1 标记缺少模块名"))
                continue
            if not desc:
                problems.append(PublicApiProblem(path=path, lineno=lineno, module=module, reason="tier1 标记缺少说明"))
                continue
            if not scenario:
                problems.append(PublicApiProblem(path=path, lineno=lineno, module=module, reason="tier1 标记缺少常见场景"))
                continue

            entrypoints.append(
                PublicApiEntrypointMarker(
                    tier=got_tier,
                    order=order,
                    module=module,
                    description=desc,
                    common_scenario=scenario,
                    marker_path=path,
                    marker_lineno=lineno,
                )
            )

    by_module: dict[str, PublicApiEntrypointMarker] = {}
    for entry in entrypoints:
        if entry.module in by_module:
            first = by_module[entry.module]
            problems.append(
                PublicApiProblem(
                    path=entry.marker_path,
                    lineno=entry.marker_lineno,
                    module=entry.module,
                    reason="重复的 tier1 标记（已在 {}:{} 声明）".format(
                        str(first.marker_path.relative_to(repo_root)).replace("\\", "/"),
                        first.marker_lineno,
                    ),
                )
            )
            continue
        by_module[entry.module] = entry

    discovered = sorted(by_module.values(), key=lambda e: (int(e.order), str(e.module)))
    if not discovered and not problems:
        problems.append(
            PublicApiProblem(
                path=repo_root / "src" / "scalim",
                lineno=1,
                module="",
                reason="未找到 tier{} 入口标记（应位于 `src/scalim/**/__init__.py`）".format(int(tier)),
            )
        )

    return tuple(discovered), tuple(sorted(problems, key=lambda p: (str(p.path), int(p.lineno), str(p.module), str(p.reason))))


def resolve_module_source_path(repo_root: Path, module: str) -> Optional[Path]:
    """将点分“模块名”解析为 `src/` 下的 `.py` 源文件路径.

    返回:
      - 包：`<repo>/src/<module path>/__init__.py`
      - 模块文件：`<repo>/src/<module path>.py`
      - 未找到则返回 `None`
    """

    src_root = repo_root / "src"
    parts = [p for p in str(module).split(".") if p]
    if not parts:
        return None
    base = src_root.joinpath(*parts)
    pkg_init = base / "__init__.py"
    if pkg_init.is_file():
        return pkg_init
    mod_file = base.with_suffix(".py")
    if mod_file.is_file():
        return mod_file
    return None


def _as_str_constant(node: ast.AST) -> Optional[str]:
    ast_str = getattr(ast, "Str", None)
    if ast_str is not None and isinstance(node, ast_str):  # `py<3.8`: 新版运行时已移除
        return str(getattr(node, "s", ""))
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return str(node.value)
    return None


def extract_literal_module_all(path: Path, *, repo_root: Path) -> Tuple[Optional[ModuleAllLiteral], Optional[str]]:
    """提取模块中最后一次出现的字面量 `__all__` 赋值.

    返回：`(all_literal, error_reason)`
      - `all_literal` 为 `None`：缺失 `__all__` 或无法解析为“字符串常量组成的 `list`/`tuple`”
      - `error_reason` 为 `None`：表示解析成功
    """

    rel = str(path.relative_to(repo_root)).replace("\\", "/")
    text = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text, filename=rel)
    except SyntaxError as exc:
        return None, "AST 解析失败（SyntaxError）: {}".format(exc)

    last_value: Optional[ast.AST] = None
    last_lineno: Optional[int] = None

    for node in getattr(tree, "body", []):
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
                last_value = node.value
                last_lineno = int(getattr(node, "lineno", 0) or 0) or None
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "__all__":
                last_value = node.value
                last_lineno = int(getattr(node, "lineno", 0) or 0) or None

    if last_value is None:
        return None, "缺少字面量 `__all__` 赋值"

    if isinstance(last_value, ast.List):
        kind = "list"
        elts = list(last_value.elts)
    elif isinstance(last_value, ast.Tuple):
        kind = "tuple"
        elts = list(last_value.elts)
    else:
        return (
            None,
            "`__all__` 非字面量（期望字符串常量组成的 list/tuple；当前: {}）".format(type(last_value).__name__),
        )

    values: List[str] = []
    for elt in elts:
        value = _as_str_constant(elt)
        if value is None:
            return None, "`__all__` 元素非字符串字面量（期望 string constants）"
        values.append(value)

    lineno = int(last_lineno or 1)
    return ModuleAllLiteral(values=tuple(values), kind=kind, lineno=lineno), None
