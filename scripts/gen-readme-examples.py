# ruff: noqa: T201
"""生成 `README` 受控示例注入区块与 `memory-compare` 系列 SVG."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, Optional

from notebooks.marimo.example_readme_suite.support.inject import check_readme_examples_governance, write_readme
from notebooks.marimo.example_readme_suite.support.render_chart import expected_assets, write_svg


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="生成 README 受控示例注入与图表资产.")
    parser.add_argument("--check", action="store_true", help="仅检查漂移,不写入.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    root = _repo_root()
    if args.check:
        errors = check_readme_examples_governance(root)
        if errors:
            sys.stderr.write("README 示例治理检查失败:\n")
            for item in errors:
                sys.stderr.write("  - {}\n".format(item))
            sys.stderr.write("\n修复: 运行 `just gen-readme-examples`\n")
            return 1
        sys.stdout.write("OK: README 示例注入与图表资产一致\n")
        return 0

    write_svg(root)
    readme = write_readme(root)
    sys.stdout.write("已更新:\n")
    for rel, _body in expected_assets():
        sys.stdout.write("  - {}\n".format(root / rel))
    sys.stdout.write("  - {}\n".format(readme))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
