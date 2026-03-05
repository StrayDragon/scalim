# ruff: noqa: T201
"""
检查 `src/scalim/` 下的模块文件名是否与 Python 标准库模块同名.

这是一个防护栏:避免在 `src/scalim/` 里出现容易混淆的模块命名(例如:`types.py`、`inspect.py`),
导致 `import` 时被误认为是标准库的 `types` / `inspect`.

用法:
    `python scripts/check-stdlib-module-collisions.py`

退出码:
- 0: 未发现冲突
- 1: 发现冲突
"""

import sys
import sysconfig
from pathlib import Path
from typing import Iterable, List, Set


def _iter_stdlib_paths() -> Iterable[str]:
    try:
        stdlib_path = sysconfig.get_paths().get("stdlib")
    except Exception:
        stdlib_path = None
    if stdlib_path:
        yield stdlib_path


def _collect_stdlib_module_names() -> Set[str]:
    names: Set[str] = set(sys.builtin_module_names)

    # Python 3.10+: 尽力使用更权威的标准库模块名列表.
    if hasattr(sys, "stdlib_module_names"):
        try:
            names.update(getattr(sys, "stdlib_module_names"))  # type: ignore[arg-type]
            return names
        except Exception:
            pass

    # Python 3.6 兜底: 从标准库路径枚举顶层模块/包名.
    try:
        import pkgutil
    except Exception:
        pkgutil = None  # type: ignore[assignment]

    if pkgutil is not None:
        for path in _iter_stdlib_paths():
            try:
                for module_info in pkgutil.iter_modules([path]):
                    names.add(module_info.name)
            except Exception:
                continue

    return names


def _collect_python_module_stems(root: Path) -> Set[str]:
    stems: Set[str] = set()
    for path in root.rglob("*.py"):
        stems.add(path.stem)
    return stems


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    pkg_root = repo_root / "src" / "scalim"
    if not pkg_root.exists():
        print("错误: 未找到 `src/scalim/` 目录: {}".format(pkg_root))
        return 1

    stdlib_names = _collect_stdlib_module_names()
    module_stems = _collect_python_module_stems(pkg_root)
    collisions = sorted(module_stems.intersection(stdlib_names))

    if not collisions:
        print("正常: `src/scalim/` 下未发现与标准库同名的模块文件")
        return 0

    collision_paths: List[str] = []
    for stem in collisions:
        for path in sorted(pkg_root.rglob(stem + ".py")):
            collision_paths.append(str(path.relative_to(repo_root)))

    print("错误: `src/scalim/` 下检测到与标准库同名的模块文件:")
    for p in collision_paths:
        print("  - {}".format(p))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
