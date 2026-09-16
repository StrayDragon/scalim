#!/usr/bin/env python3
"""`notebooks/marimo` 套件的 headless 对拍入口(即 `just examples` 的实现).

设计:
- `notebooks/marimo/` 只放 marimo 章节 notebook(`ch*.py`)与轨道 `registry.py`;
  本脚本承担「自动发现 → 跑对拍 → 汇总退出码」, 因此编辑器里不会出现非 notebook 的枢纽页.
- 发现规则(与 `examples-marimo` 合约一致):
  - suite = `notebooks/marimo/<demo_*|example_*>/`
  - 轨道(group) = suite 下带 `registry.py` 的 `chapters*` 目录, 顺序: 声明面 → 装配面 → 其余
  - 章节真相 = `notebooks.marimo.<suite>.<group>.registry.run_all_chapters()`

用法:
  python scripts/run-marimo-notebooks.py                     # 静默汇总(与 CI 一致)
  QA_VERBOSE=1 python scripts/run-marimo-notebooks.py        # 逐章 PASS/FAIL 明细
  SCALIM_EXAMPLES_SUITES=demo_big_data_report python scripts/run-marimo-notebooks.py
  SCALIM_EXAMPLES_JOBS=2 python scripts/run-marimo-notebooks.py

QA_VERBOSE 三档(与 justfile/`scripts/qa-step.sh` 语义一致):
  空/"0"/"off"/"false"/"no" → 静默: 仅打印汇总行(逐章明细不外显)
  "1"                       → 逐章 PASS/FAIL 明细
  其他真值(如 "2")           → 逐章 PASS/FAIL 明细(同 "1"; 保留给 justfile L2 全量档)

输出合约:
- 静默模式只打印汇总行; 失败时把失败详情写 `stderr`.
- 退出码: 0 全通过 / 1 存在失败.
- 经 `just examples` 调用时, L0 档由 just 层统一捕获: 通过仅 `[pass]` 一行, 失败全量 dump(见 `scripts/qa-step.sh`).
"""

from __future__ import annotations

import importlib
import logging
import multiprocessing as mp
import os
import sys
from concurrent.futures import Future, ProcessPoolExecutor
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult
from scalim_misc.examples.harness import exit_code, format_results, summarize_failures

_NOISY_LOGGERS: Tuple[str, ...] = (
    "scalim.execution.executor.runtime.runtime",
    "scalim.derived_outputs",
    "scalim.ob.presets.row_gap",
    "scalim.sinks.sink_csv",
)

# 轨道展示/执行顺序: 声明面 → 装配面 → 其余(场景面等)
_GROUP_ORDER: Dict[str, int] = {"chapters_of_yaml_dsl": 0, "chapters_of_ir": 1}


def _is_verbose() -> bool:
    raw = str(os.environ.get("QA_VERBOSE") or "").strip().lower()
    if not raw:
        return False
    return raw not in {"", "0", "false", "no", "off"}


def _is_ci() -> bool:
    raw = str(os.environ.get("CI") or "").strip().lower()
    return bool(raw) and raw not in {"0", "false", "no"}


def _parse_jobs() -> int:
    raw = str(os.environ.get("SCALIM_EXAMPLES_JOBS") or "").strip()
    if raw:
        return max(1, int(raw))
    return 1 if _is_ci() else 2


def _parse_suites_whitelist() -> Sequence[str] | None:
    raw = str(os.environ.get("SCALIM_EXAMPLES_SUITES") or "").strip()
    if not raw:
        return None
    parts = [str(item).strip() for item in raw.replace(";", ",").split(",")]
    tokens = sorted({token for token in parts if token})
    return tokens or None


def discover_suites(*, marimo_root: Path) -> List[str]:
    """发现套件目录: 前缀 `demo_`/`example_` 且至少含 1 个 `.py`."""
    suites: List[str] = []
    for path in marimo_root.iterdir():
        if not path.is_dir():
            continue
        name = str(path.name)
        if not (name.startswith("demo_") or name.startswith("example_")):
            continue
        # 防御: 本地残留空目录/中间产物(无 `.py`)不应被识别为 suite.
        if not any(path.rglob("*.py")):
            continue
        suites.append(name)
    return sorted(suites)


def discover_chapter_groups(*, suite_dir: Path) -> List[str]:
    """发现轨道目录: `chapters*` 且带 `registry.py`, 按 声明面 → 装配面 → 其余 排序."""
    groups: List[str] = []
    for path in suite_dir.iterdir():
        if not path.is_dir():
            continue
        group_id = str(path.name)
        if not group_id.startswith("chapters"):
            continue
        if (path / "registry.py").is_file():
            groups.append(group_id)
    return sorted(groups, key=lambda group_id: (_GROUP_ORDER.get(group_id, 2), group_id))


def _configure_logging() -> None:
    # examples harness 降噪: 默认 ERROR; QA_VERBOSE 时回退 WARNING(与 check 脚本 quiet 面独立).
    logging.basicConfig(level=logging.WARNING)
    level = logging.WARNING if _is_verbose() else logging.ERROR
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(level)


def _failure(example_id: str, summary: str, details: Dict[str, object]) -> ExampleResult:
    return ExampleResult(
        example_id=example_id,
        passed=False,
        kind=EXAMPLE_KIND_ORACLE,
        summary=summary,
        details=details,
    )


def run_suite(suite_id: str) -> List[ExampleResult]:
    """按轨道跑完一个套件的全部章节对拍(真相在各轨道 `registry.run_all_chapters()`)."""
    _configure_logging()

    suite_dir = Path(".").resolve() / "notebooks" / "marimo" / str(suite_id)
    if not suite_dir.is_dir():
        return [_failure("suite/{}".format(suite_id), "suite directory missing: {}".format(suite_dir), {"suite_dir": str(suite_dir)})]

    groups = discover_chapter_groups(suite_dir=suite_dir)
    if not groups:
        return [
            _failure(
                "suite/{}".format(suite_id),
                "no chapter groups found (expected `chapters*/registry.py`)",
                {"suite_dir": str(suite_dir)},
            )
        ]

    print("[suite] {} :: groups={}".format(suite_id, ", ".join(groups)))
    all_results: List[ExampleResult] = []
    for group_id in groups:
        registry_mod = "notebooks.marimo.{}.{}.registry".format(suite_id, group_id)
        try:
            reg = importlib.import_module(registry_mod)
            results = list(reg.run_all_chapters())
        except Exception as exc:  # noqa: BLE001
            all_results.append(
                _failure(
                    "{}/{}".format(suite_id, group_id),
                    "{}: {}".format(type(exc).__name__, exc),
                    {"registry_module": registry_mod, "exc_type": type(exc).__name__, "message": str(exc)},
                )
            )
            continue
        print("  [group] {} :: {} chapters".format(group_id, len(results)))
        all_results.extend(results)
    # 说明:
    # - 章节可能把局部函数/闭包等对象放入 `details`,导致多进程返回时无法 pickle。
    # - gate 输出仅依赖 example_id/passed/kind/summary,因此在 runner 边界主动丢弃 details。
    return [
        ExampleResult(
            example_id=str(r.example_id),
            passed=bool(r.passed),
            kind=str(r.kind or ""),
            summary=str(r.summary or ""),
            details=None,
        )
        for r in all_results
    ]


def _resolve_suites(*, marimo_root: Path) -> List[str]:
    suites = discover_suites(marimo_root=marimo_root)
    if not suites:
        msg = "no suites discovered under {}".format(marimo_root)
        raise RuntimeError(msg)
    whitelist = _parse_suites_whitelist()
    if whitelist is None:
        return suites
    unknown = sorted(set(whitelist) - set(suites))
    if unknown:
        msg = "unknown suites in `SCALIM_EXAMPLES_SUITES`: {} (known: {})".format(", ".join(unknown), ", ".join(suites))
        raise ValueError(msg)
    allowed = set(whitelist)
    return [suite_id for suite_id in suites if suite_id in allowed]


def _collect_results(suites: List[str]) -> List[ExampleResult]:
    jobs = _parse_jobs()
    if jobs <= 1 or len(suites) <= 1:
        return [result for suite_id in suites for result in run_suite(suite_id)]

    try:
        ctx = mp.get_context("fork")
    except ValueError:  # pragma: no cover  # pragma: allow-no-cover 平台无 `fork` 启动方法时回落
        ctx = mp.get_context()
    with ProcessPoolExecutor(max_workers=min(jobs, len(suites)), mp_context=ctx) as executor:
        futures: Dict[Future, str] = {executor.submit(run_suite, suite_id): suite_id for suite_id in suites}
    collected: Dict[str, List[ExampleResult]] = {}
    for future, suite_id in futures.items():
        collected[suite_id] = future.result()
    return [result for suite_id in suites for result in collected.get(suite_id, [])]


def main() -> int:
    marimo_root = Path(".").resolve() / "notebooks" / "marimo"
    suites = _resolve_suites(marimo_root=marimo_root)
    all_results = _collect_results(suites)

    verbose = _is_verbose()
    if verbose:
        for line in format_results(all_results):
            print(line)
    failures = summarize_failures(all_results)
    if failures:
        print("\n--- 失败详情 ---\n{}".format(failures), file=sys.stderr)

    total = len(all_results)
    passed = sum(1 for r in all_results if r.passed)
    if verbose:
        if not failures:
            print("\n所有示例执行完成! total={} passed={}".format(total, passed))
    elif not failures:
        # 静默模式: 仅输出汇总行,不输出每项详情
        print("所有示例执行完成! total={} passed={}".format(total, passed))
    else:
        print("示例执行完成! total={} passed={} failed={}".format(total, passed, total - passed))
    return exit_code(all_results)


if __name__ == "__main__":
    sys.exit(main())
