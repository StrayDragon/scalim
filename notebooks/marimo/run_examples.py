#!/usr/bin/env python3
"""`notebooks/marimo` 的集成对拍运行器(`just examples`).

目标:
- 快速
- 稳定
- 失败时给出章节级错误上下文

覆盖:
- `demo_big_data_report`(主线示例)
- `example_public_api_suite`(`public API` 覆盖 + 扩展点演示)
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

from notebooks.marimo.demo_big_data_report.chapters.registry import (
    all_chapter_ids as demo_all_chapter_ids,
    run_all_chapters as demo_run_all_chapters,
    run_selected_chapters as demo_run_selected_chapters,
)
from notebooks.marimo.example_public_api_suite.chapters.registry import (
    all_chapter_ids as public_api_all_chapter_ids,
    run_all_chapters as public_api_run_all_chapters,
    run_selected_chapters as public_api_run_selected_chapters,
)
from scalim_misc.examples.harness import exit_code, format_results, summarize_failures

_KNOWN_SUITES = ["demo_big_data_report", "example_public_api_suite"]


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
        choices=_KNOWN_SUITES,
        help="Run only selected suite(s). Can be repeated.",
    )
    parser.add_argument(
        "--chapter",
        action="append",
        help=(
            "Run only selected chapter(s). Can be repeated. "
            "Accepts either `<chapter_id>` or `<suite>/<chapter_id>` (e.g. `demo_big_data_report/yaml_dsl_ecommerce`)."
        ),
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
    suites = set(args.suite or list(_KNOWN_SUITES))

    if args.list:
        print("套件:")
        for suite_id in sorted(_KNOWN_SUITES):
            print("- {}".format(suite_id))
        print("\n`demo_big_data_report` 章节:")
        for chapter_id in demo_all_chapter_ids():
            print("- {}".format(chapter_id))
        print("\n`example_public_api_suite` 章节:")
        for chapter_id in public_api_all_chapter_ids():
            print("- {}".format(chapter_id))
        return 0

    all_results = []

    chapter_args = list(args.chapter or [])
    chapter_map: dict[str, list[str]] = {suite_id: [] for suite_id in _KNOWN_SUITES}
    unscoped: list[str] = []
    for raw in chapter_args:
        item = str(raw)
        if "/" in item:
            suite_id, chapter_id = item.split("/", 1)
        elif ":" in item:
            suite_id, chapter_id = item.split(":", 1)
        else:
            suite_id, chapter_id = "", item
        suite_id = suite_id.strip()
        chapter_id = chapter_id.strip()
        if suite_id and suite_id in chapter_map:
            chapter_map[suite_id].append(chapter_id)
        else:
            unscoped.append(item)

    if unscoped:
        available_by_suite = {
            "demo_big_data_report": set(demo_all_chapter_ids()),
            "example_public_api_suite": set(public_api_all_chapter_ids()),
        }
        for item in unscoped:
            hit = False
            for suite_id in suites:
                if item in available_by_suite.get(suite_id, set()):
                    chapter_map[suite_id].append(item)
                    hit = True
            if not hit:
                msg = "unknown chapter (not found in selected suites): {}".format(item)
                raise ValueError(msg)

    if "demo_big_data_report" in suites:
        wanted = chapter_map["demo_big_data_report"]
        demo_results = demo_run_selected_chapters(chapter_ids=wanted) if wanted else demo_run_all_chapters()
        all_results.extend(demo_results)

    if "example_public_api_suite" in suites:
        wanted = chapter_map["example_public_api_suite"]
        public_api_results = public_api_run_selected_chapters(chapter_ids=wanted) if wanted else public_api_run_all_chapters()
        all_results.extend(public_api_results)

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
