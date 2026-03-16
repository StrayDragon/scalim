#!/usr/bin/env python3
"""`notebooks/marimo` 的集成对拍运行器(`just examples`).

目标:
- 快速
- 稳定
- 失败时给出章节级错误上下文

覆盖:
- `demo_big_data_report`(主线示例)
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]
repo_root_str = str(repo_root)
if repo_root_str not in sys.path:
    sys.path.insert(0, repo_root_str)

from notebooks.marimo.demo_big_data_report.chapters.registry import run_all_chapters, run_selected_chapters
from scalim_misc.examples.harness import exit_code, format_results, summarize_failures


def _configure_logging() -> None:
    logging.basicConfig(level=logging.WARNING)
    noisy_loggers = [
        "scalim.execution.executor.runtime.runtime",
        "scalim.ob.presets.row_gap",
        "scalim.sinks.sink_csv",
    ]
    for name in noisy_loggers:
        logging.getLogger(name).setLevel(logging.ERROR if name == "scalim.sinks.sink_csv" else logging.WARNING)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scalim examples runner (headless, deterministic).")
    parser.add_argument(
        "--suite",
        action="append",
        choices=["demo_big_data_report"],
        help="Run only selected suite(s). Can be repeated.",
    )
    parser.add_argument(
        "--chapter",
        action="append",
        help="Run only selected demo chapter id(s). Only applies to demo_big_data_report. Can be repeated.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available suites/chapters and exit.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    _configure_logging()

    args = _parse_args(list(argv or sys.argv[1:]))
    suites = set(args.suite or ["demo_big_data_report"])

    if args.list:
        from notebooks.marimo.demo_big_data_report.chapters.registry import all_chapter_ids

        print("套件:")
        for suite_id in sorted(suites):
            print("- {}".format(suite_id))
        print("\n`demo_big_data_report` 章节:")
        for chapter_id in all_chapter_ids():
            print("- {}".format(chapter_id))
        return 0

    all_results = []

    if "demo_big_data_report" in suites:
        if args.chapter:
            demo_results = run_selected_chapters(chapter_ids=args.chapter)
        else:
            demo_results = run_all_chapters()
        all_results.extend(demo_results)

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
