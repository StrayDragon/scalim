"""检查: `ENTRY` 热点路径函数级复杂度硬闸 (`cognitive` + `cyclomatic`).

用法:
- `uv run --with radon --with cognitive-complexity python scripts/check-complexity.py`
- `uv run --with radon --with cognitive-complexity python scripts/check-complexity.py --check`
- `uv run --with radon --with cognitive-complexity python scripts/check-complexity.py --check --quiet`
- `uv run --with radon --with cognitive-complexity python scripts/check-complexity.py --radar`

输出合约:
- `--check` 只控制退出码(超过阈值时非 0); 不隐含静默.
- `--quiet` 且通过时不写 `stdout`; 失败时仍写 `stderr`.
- `--radar` 对更广 `src/scalim` 打印 `top-N`; 始终以退出码 0 结束(工具缺失除外).
- 非 `--check`/`--radar` 模式下默认打印 `ENTRY` 报告.

阈值 `SSOT`(与 `governance-module-organization` `r253` / `docs/doc/dev/complexity-qa-harness.md` 同数):
- `MAX_COGNITIVE` / `MAX_CYCLOMATIC` = `ENTRY` 基线最大值 + 余量
- 工具: `radon` (`McCabe`) + `cognitive-complexity` (`Sonar`); 不进应用 `dependencies`
"""

import argparse
import ast
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple


# 钉死的 CLI 工具版本(非应用依赖).
_RADON_SPEC = "radon==6.0.1"
_COGNITIVE_SPEC = "cognitive-complexity==1.3.0"

# `HARD` `ENTRY` = 今日 `check-module-size` `_HOTSPOT_LIMITS` 路径集合.
ENTRY_PATHS = (
    "src/scalim/workflow/execute.py",
    "src/scalim/execution/output_composition",
    "src/scalim/execution/derived_outputs.py",
    "src/scalim/dsl/yaml_dsl/_internal/config_parsing/parsers/outputs.py",
    "src/scalim/dsl/yaml_dsl/_internal/config_parsing/validators/sources.py",
    "src/scalim/dsl/yaml_dsl/schema_dsl/models/outputs.py",
    "src/scalim/dsl/yaml_dsl/runtime/output_composition_yaml.py",
    "src/scalim/dsl/yaml_dsl/workflow_config/_parse.py",
)

# 基线 (2026-08-02 `ENTRY` 扫描): max_cognitive=75, max_cyclomatic=39; 余量 +5.
MAX_COGNITIVE = 80
MAX_CYCLOMATIC = 44

RADAR_ROOT = "src/scalim"
RADAR_TOP_N = 20


@dataclass(frozen=True)
class FuncComplexity:
    path: str
    qualname: str
    lineno: int
    cognitive: int
    cyclomatic: int


def _script_path() -> Path:
    return Path(__file__).resolve()


def _try_import_tools() -> bool:
    try:
        import cognitive_complexity.api  # noqa: F401
        import radon.complexity  # noqa: F401

        return True
    except ImportError:
        return False


def _iter_py_files(path: Path) -> Iterable[Path]:
    if path.is_dir():
        for child in sorted(path.rglob("*.py")):
            if "__pycache__" in child.parts:
                continue
            if "vendor" in child.parts:
                continue
            yield child
        return
    yield path


def _qualname(classname, name):
    # type: (Optional[str], str) -> str
    if classname:
        return "{}.{}".format(classname, name)
    return name


def _collect_file(repo_root, path):
    # type: (Path, Path) -> List[FuncComplexity]
    from cognitive_complexity.api import get_cognitive_complexity
    from radon.complexity import cc_visit
    from radon.visitors import Function as RadonFunction

    rel = str(path.relative_to(repo_root)).replace("\\", "/")
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise ValueError("{}: 语法错误: {}".format(rel, exc))

    cog_by_key = {}  # type: dict
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            key = (int(node.lineno), node.name)
            cog_by_key[key] = int(get_cognitive_complexity(node))

    rows = []  # type: List[FuncComplexity]
    for block in cc_visit(source):
        if not isinstance(block, RadonFunction):
            continue
        classname = getattr(block, "classname", None) or None
        name = str(block.name)
        lineno = int(getattr(block, "lineno", 0) or 0)
        cyclo = int(block.complexity)
        cog = int(cog_by_key.get((lineno, name), 0))
        rows.append(
            FuncComplexity(
                path=rel,
                qualname=_qualname(classname, name),
                lineno=lineno,
                cognitive=cog,
                cyclomatic=cyclo,
            )
        )
    return rows


def collect_paths(repo_root, rel_paths):
    # type: (Path, Sequence[str]) -> List[FuncComplexity]
    rows = []  # type: List[FuncComplexity]
    for rel in rel_paths:
        path = repo_root / rel
        if not path.exists():
            raise FileNotFoundError(rel)
        for py in _iter_py_files(path):
            rows.extend(_collect_file(repo_root, py))
    return rows


def _violations(rows, max_cognitive, max_cyclomatic):
    # type: (Sequence[FuncComplexity], int, int) -> List[Tuple[FuncComplexity, str]]
    hits = []  # type: List[Tuple[FuncComplexity, str]]
    for row in rows:
        reasons = []  # type: List[str]
        if row.cognitive > max_cognitive:
            reasons.append("cognitive={} > {}".format(row.cognitive, max_cognitive))
        if row.cyclomatic > max_cyclomatic:
            reasons.append("cyclomatic={} > {}".format(row.cyclomatic, max_cyclomatic))
        if reasons:
            hits.append((row, "; ".join(reasons)))
    return hits


def _format_row(row):
    # type: (FuncComplexity) -> str
    return "{}:{} {} cognitive={} cyclomatic={}".format(row.path, row.lineno, row.qualname, row.cognitive, row.cyclomatic)


def _print_top(rows, key_name, top_n, stream=None):
    # type: (Sequence[FuncComplexity], str, int, Optional[object]) -> None
    if stream is None:
        stream = sys.stdout
    if key_name == "cognitive":
        ordered = sorted(rows, key=lambda r: (-r.cognitive, -r.cyclomatic, r.path, r.lineno))
    else:
        ordered = sorted(rows, key=lambda r: (-r.cyclomatic, -r.cognitive, r.path, r.lineno))
    print("top-{} by {}".format(top_n, key_name), file=stream)  # force-en
    for row in ordered[:top_n]:
        print("  - {}".format(_format_row(row)), file=stream)


def _baseline_summary(rows):
    # type: (Sequence[FuncComplexity]) -> dict
    if not rows:
        return {"max_cognitive": 0, "max_cyclomatic": 0, "n_functions": 0, "top_cognitive": [], "top_cyclomatic": []}
    by_cog = sorted(rows, key=lambda r: (-r.cognitive, r.path, r.lineno))
    by_cyc = sorted(rows, key=lambda r: (-r.cyclomatic, r.path, r.lineno))

    def _brief(row):
        # type: (FuncComplexity) -> dict
        return {
            "path": row.path,
            "lineno": row.lineno,
            "qualname": row.qualname,
            "cognitive": row.cognitive,
            "cyclomatic": row.cyclomatic,
        }

    return {
        "max_cognitive": by_cog[0].cognitive,
        "max_cyclomatic": by_cyc[0].cyclomatic,
        "n_functions": len(rows),
        "top_cognitive": [_brief(r) for r in by_cog[:10]],
        "top_cyclomatic": [_brief(r) for r in by_cyc[:10]],
        "thresholds": {"MAX_COGNITIVE": MAX_COGNITIVE, "MAX_CYCLOMATIC": MAX_CYCLOMATIC},
        "entry_paths": list(ENTRY_PATHS),
    }


def main(argv=None):
    # type: (Optional[Sequence[str]]) -> int
    raw_argv = list(sys.argv[1:] if argv is None else argv)

    p = argparse.ArgumentParser(description="检查: ENTRY 热点路径函数级复杂度硬闸 (cognitive + cyclomatic).")
    p.add_argument("--root", default=".", help="仓库根目录(默认: .).")
    p.add_argument("--check", action="store_true", help="超过阈值时直接失败.")
    p.add_argument("--quiet", action="store_true", help="静默模式: 通过时不向 stdout 写报告; 失败仍写 stderr.")
    p.add_argument("--radar", action="store_true", help="软雷达: 扫描 src/scalim top-N; 始终成功退出.")
    p.add_argument("--top", type=int, default=RADAR_TOP_N, help="雷达/报告 top-N (默认: {}).".format(RADAR_TOP_N))
    p.add_argument("--max-cognitive", type=int, default=MAX_COGNITIVE, help="cognitive 硬阈 (默认: {}).".format(MAX_COGNITIVE))
    p.add_argument("--max-cyclomatic", type=int, default=MAX_CYCLOMATIC, help="cyclomatic 硬阈 (默认: {}).".format(MAX_CYCLOMATIC))
    p.add_argument("--write-baseline", default="", help="可选: 将 ENTRY 基线摘要写入 JSON 路径.")
    args = p.parse_args(raw_argv)

    if not _try_import_tools():
        if os.environ.get("SCALIM_COMPLEXITY_BOOTSTRAPPED") == "1":
            print(
                "[错误] 缺少 `radon`/`cognitive-complexity`; 请用 `uv run --with radon --with cognitive-complexity` 或 `uvx` 运行.",
                file=sys.stderr,
            )
            return 2
        env = dict(os.environ)
        env["SCALIM_COMPLEXITY_BOOTSTRAPPED"] = "1"
        cmd = [
            "uvx",
            "--from",
            _RADON_SPEC,
            "--with",
            _COGNITIVE_SPEC,
            "python",
            str(_script_path()),
        ] + raw_argv
        try:
            return int(subprocess.call(cmd, env=env))
        except OSError as exc:
            print(
                "[错误] 缺少复杂度工具且无法通过 `uvx` 启动: {}".format(exc),
                file=sys.stderr,
            )
            return 2

    repo_root = Path(str(args.root)).resolve()
    try:
        if args.radar:
            rows = collect_paths(repo_root, [RADAR_ROOT])
        else:
            rows = collect_paths(repo_root, ENTRY_PATHS)
    except FileNotFoundError as exc:
        print("[错误] 复杂度护栏找不到目标路径: {}".format(exc), file=sys.stderr)
        return 2
    except ValueError as exc:
        print("[错误] {}".format(exc), file=sys.stderr)
        return 2

    if args.write_baseline:
        summary = _baseline_summary(rows if not args.radar else collect_paths(repo_root, ENTRY_PATHS))
        out = Path(str(args.write_baseline))
        if not out.is_absolute():
            out = repo_root / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if args.radar:
        if not args.quiet:
            print("复杂度雷达 ({})".format(RADAR_ROOT))
            print("")
            _print_top(rows, "cognitive", int(args.top))
            print("")
            _print_top(rows, "cyclomatic", int(args.top))
        return 0

    hits = _violations(rows, int(args.max_cognitive), int(args.max_cyclomatic))

    if not args.check:
        if not args.quiet:
            print("复杂度 `ENTRY` 报告")
            print("  `MAX_COGNITIVE`={} `MAX_CYCLOMATIC`={}".format(args.max_cognitive, args.max_cyclomatic))
            print("")
            _print_top(rows, "cognitive", int(args.top))
            print("")
            _print_top(rows, "cyclomatic", int(args.top))
            if hits:
                print("")
                print("[警告] 超过阈值: {}".format(len(hits)))
                for row, reason in hits:
                    print("  - {} ({})".format(_format_row(row), reason))
        return 0

    if hits:
        print(
            "[错误] `ENTRY` 函数复杂度超过阈值 (`cognitive`<={} / `cyclomatic`<={}); 请降复杂度或按职责拆分.".format(
                args.max_cognitive, args.max_cyclomatic
            ),
            file=sys.stderr,
        )
        for row, reason in hits:
            print("  - {} ({})".format(_format_row(row), reason), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
