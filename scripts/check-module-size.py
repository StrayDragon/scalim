"""检查热点模块体量护栏(避免继续增长; 提示拆分).

用法:
- `uv run python scripts/check-module-size.py`
- `uv run python scripts/check-module-size.py --check`
- `uv run python scripts/check-module-size.py --check --quiet`

输出合约:
- `--check` 只控制退出码(超过阈值时非 0); 不隐含静默.
- `--quiet` 且通过时不写 `stdout`; 失败时仍写 `stderr`.
- 非 `--check` 模式下 `--quiet` 跳过信息性报告.
"""

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
    # output_composition 已拆分为子包; 按目录聚合统计以保持护栏意义.
    "src/scalim/execution/output_composition": 1700,
    # `derived_outputs`: 当前约 1260 行; 上限留约 15% 余量,拆分走后续 `SDD`.
    "src/scalim/execution/derived_outputs.py": 1450,
    # `yaml_dsl` `outputs`/`sources` 集群: 当前均 >1000 行; 上限约 15% 余量,禁止无审阅继续膨胀.
    "src/scalim/dsl/yaml_dsl/_internal/config_parsing/parsers/outputs.py": 1375,
    "src/scalim/dsl/yaml_dsl/_internal/config_parsing/validators/sources.py": 1340,
    "src/scalim/dsl/yaml_dsl/schema_dsl/models/outputs.py": 1230,
    "src/scalim/dsl/yaml_dsl/runtime/output_composition_yaml.py": 1200,
    # 试点拆分模块: 保持低于通用阈值.
    "src/scalim/dsl/yaml_dsl/workflow_config/_parse.py": 1000,
}


def _count_lines(path: Path) -> int:
    if path.is_dir():
        total = 0
        for child in sorted(path.rglob("*.py")):
            if "__pycache__" in child.parts:
                continue
            total += _count_lines(child)
        return total

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
    p.add_argument("--root", default=".", help="仓库根目录(默认: .).")
    p.add_argument("--check", action="store_true", help="超过阈值时直接失败.")
    p.add_argument("--quiet", action="store_true", help="静默模式: 通过时不向 stdout 写报告; 失败仍写 stderr.")
    args = p.parse_args(argv)

    repo_root = Path(str(args.root)).resolve()
    try:
        rows = _collect(repo_root)
    except FileNotFoundError as exc:
        print("[错误] 模块体量护栏找不到目标文件: {}".format(exc), file=sys.stderr)
        return 2

    too_large: List[ModuleSize] = [row for row in rows if row.lines > row.limit]

    if not args.check:
        if not args.quiet:
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
