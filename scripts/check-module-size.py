import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class ModuleSize:
    path: Path
    rel_path: str
    lines: int
    limit: int


_HOTSPOT_LIMITS: Dict[str, int] = {
    # 热点模块: 防止继续膨胀; 拆分在后续变更推进.
    "src/scalim/workflow/execute.py": 1920,
    "src/scalim/execution/output_composition.py": 1377,
    # 试点拆分模块: 保持低于通用阈值.
    "src/scalim/dsl/by_yaml/workflow_config/_parse.py": 1000,
}


def _count_lines(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    return len(text.splitlines())


def _collect(repo_root: Path) -> List[ModuleSize]:
    rows: List[ModuleSize] = []
    for rel, limit in sorted(_HOTSPOT_LIMITS.items()):
        path = repo_root / rel
        if not path.exists():
            raise FileNotFoundError(rel)
        rows.append(ModuleSize(path=path, rel_path=rel, lines=_count_lines(path), limit=int(limit)))
    return rows


def _format_row(row: ModuleSize) -> str:
    status = "正常" if row.lines <= row.limit else "超限"
    return "{}: 行数={} 上限={} 状态={}".format(row.rel_path, row.lines, row.limit, status)


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="检查: 热点模块体量护栏(避免继续增长; 提示拆分).")
    p.add_argument("--check", action="store_true", help="超过阈值时直接失败.")
    args = p.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[1]
    try:
        rows = _collect(repo_root)
    except FileNotFoundError as exc:
        print("[错误] 模块体量护栏找不到目标文件: {}".format(exc), file=sys.stderr)
        return 2

    too_large: List[ModuleSize] = [row for row in rows if row.lines > row.limit]

    if not args.check:
        print("模块体量报告")
        print("")
        for row in rows:
            print("  - {}".format(_format_row(row)))
        if too_large:
            print("")
            print("[警告] 超过阈值: {}".format(len(too_large)))
            for row in too_large:
                print("  - {}".format(_format_row(row)))
        return 0

    if too_large:
        print("[错误] 热点模块超过体量阈值; 请按领域+阶段拆分后再提交.", file=sys.stderr)
        for row in too_large:
            print("  - {}".format(_format_row(row)), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
