#!/usr/bin/env python3
"""`demo_big_data_report` 的集成对拍运行器.

作为 `just examples` 的唯一入口:
- 快速
- 稳定
- 失败时给出章节级错误上下文
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[3]
repo_root_str = str(repo_root)
if repo_root_str not in sys.path:
    sys.path.insert(0, repo_root_str)

from scalim_misc.demo_big_data_report.chapters.registry import run_all_chapters


def _configure_logging() -> None:
    logging.basicConfig(level=logging.WARNING)
    noisy_loggers = [
        "scalim.execution.executor.runtime.runtime",
        "scalim.ob.presets.row_gap",
        "scalim.sinks.sink_csv",
    ]
    for name in noisy_loggers:
        logging.getLogger(name).setLevel(logging.ERROR if name == "scalim.sinks.sink_csv" else logging.WARNING)


def main() -> int:
    _configure_logging()

    demo_dir = Path(__file__).parent
    yaml_path = demo_dir / "by_yaml_dsl" / "ecommerce_report.yaml"
    results = run_all_chapters(yaml_path=yaml_path)
    failed = [r for r in results if not r.passed]

    for r in results:
        status = "PASS" if r.passed else "FAIL"
        first_line = r.summary.splitlines()[0] if r.summary else ""
        print("[{}] {} - {}".format(status, r.chapter_id, first_line))

    if failed:
        print("\n--- 失败详情 ---", file=sys.stderr)
        for r in failed:
            print("\n[FAIL] {}\n{}".format(r.chapter_id, r.summary), file=sys.stderr)
        return 1

    print("\n所有示例执行完成!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
