"""从 marimo 章节 notebook 提取「可见代码 cell」, 供文档注入投影复用 (单一真相在 cells)。

投影规则 (与 marimo 自身的展示语义一致):

- 只取 `@app.cell` / `@app.cell(...)` 装饰的模块级函数体;
- `@app.cell(hide_code=True)` 的 cell 在 marimo 里本就折叠, 投影同样跳过;
- cell 顶层的 `return ...` (marimo 的 cell 输出管道) 在投影中略去,
  使结果可直接作为普通 `.py` 脚本阅读/运行; 嵌套函数内的 `return` 保留;
- 顺序 = 文件内定义顺序 (即读者的阅读顺序)。
"""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path


def _is_app_cell(node: ast.FunctionDef) -> bool:
    """匹配 `@app.cell` 与 `@app.cell(...)` 两种写法 (marimo 两者都会生成)。"""
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if isinstance(target, ast.Attribute) and target.attr == "cell":
            return True
    return False


def _is_hidden(node: ast.FunctionDef) -> bool:
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute) and decorator.func.attr == "cell":
            for keyword in decorator.keywords:
                if keyword.arg == "hide_code":
                    return getattr(keyword.value, "value", None) is True
    return False


def _drop_cell_returns(body: str) -> str:
    """去掉 cell 顶层 `return ...` (按语句行范围整段删除; 嵌套 `return` 保留)。"""
    lines = body.splitlines()
    dropped: set[int] = set()
    for stmt in ast.parse(body).body:
        if isinstance(stmt, ast.Return):
            dropped.update(range(stmt.lineno, (stmt.end_lineno or stmt.lineno) + 1))
    kept = [line for number, line in enumerate(lines, start=1) if number not in dropped]
    return "\n".join(kept).strip("\n")


def extract_visible_cell_sources(path: str | Path) -> list[str]:
    """返回章节 notebook 中所有「非 hide_code」cell 的代码体 (按文件顺序, 已去缩进)。"""
    p = path if isinstance(path, Path) else Path(path)
    source = p.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source)
    cells: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or not _is_app_cell(node):
            continue
        if _is_hidden(node) or not node.body:
            continue
        # 从第一条语句开始 (跳过 `@app.cell` 装饰器与可能跨行的 `def` 签名)
        start = node.body[0].lineno - 1
        end = node.body[-1].end_lineno or node.body[-1].lineno
        body = textwrap.dedent("\n".join(lines[start:end]))
        cells.append(_drop_cell_returns(body))
    return cells
