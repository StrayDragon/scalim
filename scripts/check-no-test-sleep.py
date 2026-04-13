"""门禁：禁止在 `tests/` 中使用 `time.sleep`，除非显式加入白名单。

用法：
    `uv run python scripts/check-no-test-sleep.py --check`
"""

import argparse
import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Set

TESTS_ROOT = Path(__file__).resolve().parents[1] / "tests"

ALLOWLIST: Set[str] = {
    "tests/fixtures/workflow_loaders.py",
}


@dataclass(frozen=True)
class SleepHit:
    path: str
    line: int
    column: int


def _find_sleep_calls(path: Path) -> List[SleepHit]:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        return []
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        return []

    hits: List[SleepHit] = []

    class _Visitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
            fn = node.func
            if isinstance(fn, ast.Attribute) and fn.attr == "sleep":
                if isinstance(fn.value, ast.Name) and fn.value.id == "time":
                    hits.append(SleepHit(path=str(path), line=node.lineno, column=node.col_offset))
            self.generic_visit(node)

    _Visitor().visit(tree)
    return hits


def main() -> None:
    parser = argparse.ArgumentParser(description="检查 `tests/` 中的 `time.sleep` 使用情况")
    parser.add_argument("--check", action="store_true", help="发现违规时以非零退出码失败")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    all_hits: List[SleepHit] = []
    for py_file in sorted(TESTS_ROOT.rglob("*.py")):
        rel = str(py_file.relative_to(repo_root))
        if rel in ALLOWLIST:
            continue
        all_hits.extend(_find_sleep_calls(py_file))

    if not all_hits:
        print("`check-no-test-sleep`：通过（0 处违规）")
        return

    print("`check-no-test-sleep`：发现 {} 处违规：".format(len(all_hits)))
    for hit in all_hits:
        rel_path = str(Path(hit.path).relative_to(repo_root))
        print("  {}:{}:{}: `time.sleep`".format(rel_path, hit.line, hit.column))

    if ALLOWLIST:
        print("\n白名单文件（已从检查中排除）：")
        for p in sorted(ALLOWLIST):
            print("  {}".format(p))
    print("\n如需新增允许路径，请更新 `scripts/check-no-test-sleep.py` 中的 `ALLOWLIST`。")

    if args.check:
        sys.exit(1)


if __name__ == "__main__":
    main()
