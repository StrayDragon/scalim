#!/usr/bin/env python3
"""`notebooks/marimo` 的集成对拍运行器(`just examples`).

目标:
- 快速
- 稳定
- 失败时给出章节级错误上下文

覆盖:
- `demo_big_data_report`(主线示例)
- `example_public_api`(公共入口示例/回归套件)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]
repo_root_str = str(repo_root)
if repo_root_str not in sys.path:
    sys.path.insert(0, repo_root_str)

from scalim_misc.demo_big_data_report.chapters.registry import run_all_chapters
from scalim_misc.examples.harness import (
    coerce_demo_chapter_results,
    exit_code,
    format_results,
    run_public_api_examples,
    summarize_failures,
)


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

    demo_dir = Path(__file__).parent / "demo_big_data_report"
    yaml_path = demo_dir / "by_yaml_dsl" / "ecommerce_report.yaml"
    demo_results = run_all_chapters(yaml_path=yaml_path)
    demo_examples = coerce_demo_chapter_results(suite_id="demo_big_data_report", results=demo_results)

    public_api_examples = run_public_api_examples()

    all_results = [*demo_examples, *public_api_examples]

    for line in format_results(all_results):
        print(line)

    failures = summarize_failures(all_results)
    if failures:
        print("\n--- 失败详情 ---\n{}".format(failures), file=sys.stderr)

    if not failures:
        print("\n所有示例执行完成!")

    return exit_code(all_results)


if __name__ == "__main__":
    raise SystemExit(main())
