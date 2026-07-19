"""检查核心事件分发映射完整性(新增事件需显式加入或忽略).

用法:
- `uv run python scripts/check-dispatch-map-completeness.py`
- `uv run python scripts/check-dispatch-map-completeness.py --check`
- `uv run python scripts/check-dispatch-map-completeness.py --check --quiet`

输出合约:
- `--check` 只控制退出码(发现缺口时非 0); 不隐含静默.
- `--quiet` 且通过时不写 `stdout`; 失败时仍写 `stderr`.
- 非 `--check` 模式下 `--quiet` 跳过信息性报告.
"""

import argparse
import sys
from typing import Iterable, List, Optional, Sequence, Set

from scalim.events import get_event_catalog
from scalim.events._catalog import WORKFLOW_EVENT_PREFIXES, WORKFLOW_SCOPE_EVENT_NAMES
from scalim.ob.observer import _DISPATCH_MAP as _OBSERVER_DISPATCH_MAP
from scalim.ob.presets.viz.workflow import _WORKFLOW_DISPATCH_MAP as _VIZ_WORKFLOW_DISPATCH_MAP


def _is_workflow_event(event_type: str) -> bool:
    raw = str(event_type or "")
    return raw in WORKFLOW_SCOPE_EVENT_NAMES or any(raw.startswith(prefix) for prefix in WORKFLOW_EVENT_PREFIXES)


def _sorted(items: Iterable[str]) -> List[str]:
    return sorted({str(x) for x in items if str(x)})


def _collect_event_types() -> Set[str]:
    return {item.name for item in get_event_catalog()}


def _missing(*, required: Set[str], provided: Set[str], ignored: Set[str]) -> List[str]:
    return _sorted(required - provided - ignored)


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="检查: 核心事件分发映射完整性校验(新增事件需显式加入或忽略).")
    p.add_argument("--check", action="store_true", help="发现缺口时直接失败.")
    p.add_argument("--quiet", action="store_true", help="静默模式: 通过时不向 stdout 写报告; 失败仍写 stderr.")
    args = p.parse_args(argv)

    # 显式忽略列表(可按需要扩展,用于强制维护者做显式决策).
    ignored_base: Set[str] = set()
    ignored_workflow: Set[str] = set()

    catalog = _collect_event_types()
    workflow_events = {name for name in catalog if _is_workflow_event(name)}
    base_events = set(catalog) - workflow_events

    base_provided = set(_OBSERVER_DISPATCH_MAP.keys())
    workflow_provided = set(_VIZ_WORKFLOW_DISPATCH_MAP.keys())

    missing_base = _missing(required=base_events, provided=base_provided, ignored=ignored_base)
    missing_workflow = _missing(required=workflow_events, provided=workflow_provided, ignored=ignored_workflow)

    if not args.check:
        if not args.quiet:
            print("分发映射完整性报告")
            print("")
            print("事件目录汇总: 总计={} 基础事件={} 工作流事件={}".format(len(catalog), len(base_events), len(workflow_events)))
            print("基础事件分发映射: 总计={}".format(len(base_provided)))
            print("可视化工作流分发映射: 总计={}".format(len(workflow_provided)))
            if missing_base:
                print("")
                print("[警告] 缺失基础事件: {}".format(len(missing_base)))
                for name in missing_base:
                    print("  - {}".format(name))
            if missing_workflow:
                print("")
                print("[警告] 缺失工作流事件: {}".format(len(missing_workflow)))
                for name in missing_workflow:
                    print("  - {}".format(name))
        return 0

    if missing_base or missing_workflow:
        print("[错误] 核心事件分发映射未覆盖完整; 新增事件需显式加入分发映射或加入忽略列表.", file=sys.stderr)
        if missing_base:
            print("缺失基础事件:", file=sys.stderr)
            for name in missing_base:
                print("  - {}".format(name), file=sys.stderr)
        if missing_workflow:
            print("缺失工作流事件:", file=sys.stderr)
            for name in missing_workflow:
                print("  - {}".format(name), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
