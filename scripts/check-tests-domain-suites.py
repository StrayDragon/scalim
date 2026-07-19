# ruff: noqa: T201
"""
检查 `tests/` 领域套件与 `tests.*` 字符串引用边界.

覆盖的静态门禁:
- `tests/` 领域套件目录必须存在(并禁止根目录平铺 `tests/test_*.py`)
- 禁止 `tests/**/test_*_additional.py`
- 仅允许 `tests.fixtures.*` 作为 YAML/工作流 字符串引用目标(禁止其它 `tests.*`)

该脚本是静态门禁:只依赖文件系统与 AST/文本扫描,不执行运行时模块的 `import`.

用法:
- `uv run python scripts/check-tests-domain-suites.py --check`
- `uv run python scripts/check-tests-domain-suites.py --check --quiet`
- `uv run python scripts/check-tests-domain-suites.py --root /path/to/repo --check`

输出合约:
- `--check` 只控制退出码(有违规则非 0); 不隐含静默.
- `--quiet` 且通过时不写 `stdout`; 有违规时仍写 `stderr`.

退出码:
- 0: 通过
- 1: 发现违规(仅在 `--check` 时)
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path


_ALLOWED_TESTS_REF_PREFIX = "tests.fixtures"

# 只匹配“独立词元”意义上的 `tests.<name>`,避免误伤 `scalim.tests.*` 等日志标识符.
_TESTS_REF_START_RE = re.compile(r"(?<![A-Za-z0-9_.])tests\.[A-Za-z_]")


@dataclass(frozen=True)
class _Violation:
    path: Path
    lineno: int
    ref: str


def _is_allowed_tests_ref(ref: str) -> bool:
    return ref == _ALLOWED_TESTS_REF_PREFIX or ref.startswith(_ALLOWED_TESTS_REF_PREFIX + ".")


def _extract_tests_refs_from_line(line: str) -> list[str]:
    refs: list[str] = []
    idx = 0
    while True:
        match = _TESTS_REF_START_RE.search(line, idx)
        if match is None:
            break
        start = match.start()
        end = start
        while end < len(line) and (line[end].isalnum() or line[end] in "._"):
            end += 1
        refs.append(line[start:end])
        idx = end
    return refs


def _scan_text(path: Path, base_lineno: int, text: str) -> list[_Violation]:
    violations: list[_Violation] = []
    for offset, line in enumerate(text.splitlines()):
        lineno = base_lineno + offset
        for ref in _extract_tests_refs_from_line(line):
            if not _is_allowed_tests_ref(ref):
                violations.append(_Violation(path=path, lineno=lineno, ref=ref))
    return violations


def _scan_python_string_literals(path: Path) -> list[_Violation]:
    text = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        msg = "tests domain suites scan failed to parse python file: {} ({})".format(path, exc)
        raise AssertionError(msg) from exc

    violations: list[_Violation] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            violations.extend(_scan_text(path, int(getattr(node, "lineno", 1)), node.value))
    return violations


def _scan_yaml_file(path: Path) -> list[_Violation]:
    violations: list[_Violation] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        for ref in _extract_tests_refs_from_line(line):
            if not _is_allowed_tests_ref(ref):
                violations.append(_Violation(path=path, lineno=lineno, ref=ref))
    return violations


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="检查 tests domain suites 目录结构与 tests.* 字符串引用边界.")
    parser.add_argument("--root", default=".", help="仓库根目录(默认: .).")
    parser.add_argument("--check", action="store_true", help="发现违规时返回非 0 退出码.")
    parser.add_argument("--quiet", action="store_true", help="静默模式: 通过时不向 stdout 写报告; 失败仍写 stderr.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    repo_root = Path(str(args.root)).resolve()
    root = repo_root / "tests"
    if not root.is_dir():
        print("[错误] 未找到 `tests/` 目录: {}".format(root), file=sys.stderr)
        return 1 if args.check else 0

    errors: list[str] = []

    required = (
        "bench",
        "execution",
        "fixtures",
        "governance",
        "integration",
        "ob",
        "planning",
        "public_api",
        "sinks",
        "support",
        "workflow",
        "yaml_dsl",
    )
    missing = [d for d in required if not (root / d).is_dir()]
    if missing:
        errors.append("缺少必要的领域套件目录: {}".format(", ".join(missing)))

    unexpected_root_tests = sorted(p.name for p in root.glob("test_*.py"))
    if unexpected_root_tests:
        errors.append("请将 `tests/{}` 移入某个领域套件目录".format(", ".join(unexpected_root_tests)))

    additional = sorted(p.relative_to(root).as_posix() for p in root.rglob("test_*_additional.py"))
    if additional:
        errors.append("请将这些文件合并回领域套件 SSOT (禁止 `*_additional`): {}".format(", ".join(additional)))

    violations: list[_Violation] = []
    for py_path in sorted(root.rglob("*.py")):
        violations.extend(_scan_python_string_literals(py_path))
    for yaml_path in sorted(list(root.rglob("*.yaml")) + list(root.rglob("*.yml"))):
        violations.extend(_scan_yaml_file(yaml_path))

    if violations:
        rendered = "\n".join(
            "{}:{}: {}".format(v.path.relative_to(repo_root).as_posix(), v.lineno, v.ref)
            for v in sorted(violations, key=lambda v: (v.path.as_posix(), v.lineno, v.ref))
        )
        errors.append(
            "发现禁止的 `tests.*` 字符串引用(仅允许 `{}`): 请将目标 callable/module 移动到 `tests/fixtures/` 并以 `{}` 形式引用.\n{}".format(
                _ALLOWED_TESTS_REF_PREFIX,
                _ALLOWED_TESTS_REF_PREFIX + ".<module>",
                rendered,
            )
        )

    if errors:
        print("[错误] `tests/` 领域套件检查失败:", file=sys.stderr)
        for msg in errors:
            print("- {}".format(msg), file=sys.stderr)
        return 1 if args.check else 0

    if not args.quiet:
        print("[通过] `tests/` 领域套件检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
