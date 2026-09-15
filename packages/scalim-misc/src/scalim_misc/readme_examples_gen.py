"""生成 `README` 受控示例注入区块，并检查生成结果是否被手改。

单一链路：README 的「第一口」全部投影自主线套件 `demo_big_data_report` 的章节：

| README 区块 | 投影来源 |
| --- | --- |
| 最小 Python 示例 | `chapters_of_ir/ch010_basics.py` 的可见 cells（代码逐 cell 投影） |
| 最小 YAML 示例 | `chapters_of_yaml_dsl/declared_yaml_dsl/min_report.yaml` + `ch005_yaml_dsl_min.py` |
| naive vs Scalim 对比 | `chapters_of_ir/ch020_memory_compare.py` |
| 性能图 | `readme_charts_gen.py`（快照 + 版本锚定外部基线数据） |
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from scalim_misc.markdown_inject import InjectBlockSpec, InjectBlockError, replace_markdown_injected_block
from scalim_misc.notebook_support.cell_source import extract_visible_cell_sources
from scalim_misc.readme_charts_gen import expected_assets

BEGIN_MIN_PYTHON = "<!-- BEGIN AUTOGEN:readme-min-python -->"
END_MIN_PYTHON = "<!-- END AUTOGEN:readme-min-python -->"
BEGIN_MIN_YAML = "<!-- BEGIN AUTOGEN:readme-min-yaml -->"
END_MIN_YAML = "<!-- END AUTOGEN:readme-min-yaml -->"
BEGIN_NAIVE = "<!-- BEGIN AUTOGEN:readme-naive-baseline -->"
END_NAIVE = "<!-- END AUTOGEN:readme-naive-baseline -->"
BEGIN_SCALIM = "<!-- BEGIN AUTOGEN:readme-scalim-path -->"
END_SCALIM = "<!-- END AUTOGEN:readme-scalim-path -->"
BEGIN_CHART = "<!-- BEGIN AUTOGEN:readme-memory-chart -->"
END_CHART = "<!-- END AUTOGEN:readme-memory-chart -->"

_MARKERS: Sequence[Tuple[str, str]] = (
    (BEGIN_MIN_PYTHON, END_MIN_PYTHON),
    (BEGIN_MIN_YAML, END_MIN_YAML),
    (BEGIN_NAIVE, END_NAIVE),
    (BEGIN_SCALIM, END_SCALIM),
    (BEGIN_CHART, END_CHART),
)

_SUITE = "notebooks/marimo/demo_big_data_report"
_CHAPTERS_OF_IR = f"{_SUITE}/chapters_of_ir"
_CHAPTERS_OF_YAML_DSL = f"{_SUITE}/chapters_of_yaml_dsl"
_MIN_PYTHON_CHAPTER = f"{_CHAPTERS_OF_IR}/ch010_basics.py"
_MEMORY_COMPARE_CHAPTER = f"{_CHAPTERS_OF_IR}/ch020_memory_compare.py"
_MIN_YAML_CHAPTER = f"{_CHAPTERS_OF_YAML_DSL}/ch005_yaml_dsl_min.py"
_MIN_YAML = f"{_CHAPTERS_OF_YAML_DSL}/declared_yaml_dsl/min_report.yaml"
_REPO_LOADER_MODULE = "scalim_misc.demo_big_data_report.min_loaders"
_USER_LOADER_MODULE = "myapp.loaders"

_GATE_NOTE = "在仓库中可用 `just examples` 运行，也可用 `just notebook` 打开"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _pointer_lines(rel_path: str, note: str) -> List[str]:
    return [
        "- 代码：[`{}`](./{})".format(rel_path, rel_path),
        "- {}".format(note),
        "",
    ]


def _chart_block() -> str:
    lines = [
        "**① 行数扫参**（1k → 1M · 20 派生列 · csv，折线看趋势）：",
        "",
        "| 内存 | 耗时 |",
        "|------|------|",
        "| ![峰值内存随行数变化：Scalim 保持约 30 MiB 平线](docs/assets/readme/external-baseline-sweep.svg?v=3) |"
        " ![总耗时随行数变化](docs/assets/readme/external-baseline-sweep-time.svg?v=3) |",
        "",
        "复现：`just bench-external-probes --runs 3` · "
        "脚本 [run_probes.py](./docs/doc/releases/repro/external-baseline/run_probes.py) · "
        "数据 [external-baseline-0.10.probes.json](./docs/doc/assets/data/external-baseline-0.10.probes.json)",
        "",
        "**② 七种典型表**（倍数 = 相对 pandas 的比值，1.0× 虚线为持平，条尾含绝对值）：",
        "",
        "| 内存 | 耗时 |",
        "|------|------|",
        "| ![七种典型表的峰值内存对比](docs/assets/readme/external-baseline-matrix.svg?v=3) |"
        " ![七种典型表的总耗时对比](docs/assets/readme/external-baseline-matrix-time.svg?v=3) |",
        "",
        "复现：`just bench-external --runs 3` · "
        "脚本 [run_ab.py](./docs/doc/releases/repro/external-baseline/run_ab.py) · "
        "数据 [external-baseline-0.10.json](./docs/doc/assets/data/external-baseline-0.10.json) · "
        "完整表格与交互图表：[外部基线对比](./docs/doc/benchmark/external-baseline.md)",
        "",
    ]
    return "\n".join(lines)


def _min_python_block(root: Path) -> str:
    """把主线 ch010 的可见 cells 逐 cell 投影为一份可复制的 Python 代码。"""
    cells = extract_visible_cell_sources(root / _MIN_PYTHON_CHAPTER)
    if not cells:
        raise InjectBlockError("主线章节 {} 未提取到可见 cell".format(_MIN_PYTHON_CHAPTER))
    lines = [
        "以下代码逐 cell 投影自主线章节（同一份真相，打开 notebook 即可就地重跑）：",
        "",
        "```python",
        "\n\n".join(cells),
        "```",
        "",
    ]
    lines.extend(_pointer_lines(_MIN_PYTHON_CHAPTER, "主线第一章：loader → `DemandIr` → `Plan` → `Engine` → 对拍；{}".format(_GATE_NOTE)))
    return "\n".join(lines)


def _min_yaml_block(root: Path) -> str:
    source = _read(root / _MIN_YAML)
    projected = source.replace(_REPO_LOADER_MODULE, _USER_LOADER_MODULE)
    if projected == source:
        raise InjectBlockError("最小 YAML SSOT 中缺少预期的仓内 loader module")
    lines = [
        "```yaml",
        projected.rstrip(),
        "```",
        "",
        "> 把 `myapp.loaders` 换成你的加载函数所在模块。这份示例会在仓库里自动运行。",
        "",
    ]
    lines.extend(
        _pointer_lines(
            _MIN_YAML_CHAPTER,
            "最小 YAML 章节：`compile()` 语义校验 + `run()` 取行对拍；{}".format(_GATE_NOTE),
        )
    )
    lines.append("- 完整配置：[`min_report.yaml`](./{})".format(_MIN_YAML))
    lines.append("")
    return "\n".join(lines)


def _compare_pointer(note: str) -> str:
    return "\n".join(_pointer_lines(_MEMORY_COMPARE_CHAPTER, "{}；{}".format(note, _GATE_NOTE)))


def _snippet_blocks(*, repo_root: Path | None = None) -> Dict[str, str]:
    root = repo_root if repo_root is not None else _repo_root()
    return {
        "min_python": _min_python_block(root),
        "min_yaml": _min_yaml_block(root),
        "naive": _compare_pointer("对比章节（naive 基线管线在 cells 内）"),
        "scalim": _compare_pointer("对比章节（scalim 窄字段管线在 cells 内）"),
        "chart": _chart_block(),
    }


def expected_readme_text(current: str, *, repo_root: Path | None = None) -> str:
    blocks = _snippet_blocks(repo_root=repo_root)
    updated = current
    specs = (
        (BEGIN_MIN_PYTHON, END_MIN_PYTHON, blocks["min_python"], "readme-min-python"),
        (BEGIN_MIN_YAML, END_MIN_YAML, blocks["min_yaml"], "readme-min-yaml"),
        (BEGIN_NAIVE, END_NAIVE, blocks["naive"], "readme-naive-baseline"),
        (BEGIN_SCALIM, END_SCALIM, blocks["scalim"], "readme-scalim-path"),
        (BEGIN_CHART, END_CHART, blocks["chart"], "readme-memory-chart"),
    )
    for begin, end, content, label in specs:
        updated = replace_markdown_injected_block(
            updated,
            spec=InjectBlockSpec(begin_marker=begin, end_marker=end, label=label),
            content=content,
        )
    return updated


def write_readme(repo_root: Path) -> Path:
    path = repo_root / "README.md"
    updated = expected_readme_text(_read(path), repo_root=repo_root)
    path.write_text(updated, encoding="utf-8")
    return path


def check_readme_injection_drift(repo_root: Path) -> List[str]:
    errors: List[str] = []
    readme = repo_root / "README.md"
    if not readme.is_file():
        return ["缺少 README.md"]
    text = _read(readme)
    for begin, end in _MARKERS:
        if begin not in text:
            errors.append("README.md 缺少必需标记: {}".format(begin))
        if end not in text:
            errors.append("README.md 缺少必需标记: {}".format(end))
    if errors:
        return errors
    try:
        expected = expected_readme_text(text, repo_root=repo_root)
    except InjectBlockError as exc:
        return [str(exc)]
    if expected != text:
        errors.append("README.md AUTOGEN 区块已漂移;请运行 `just gen-readme-examples`(或 `just gen-docs`)")
    for rel, want in expected_assets():
        svg = repo_root / rel
        if not svg.is_file():
            errors.append("缺少图表资产: {}".format(rel.as_posix()))
            continue
        got = _read(svg)
        if got != want:
            errors.append("图表资产已漂移: {};请运行 `just gen-readme-examples`".format(rel.as_posix()))
    return errors


def _strip_autogen_blocks(text: str) -> List[str]:
    outside: List[str] = []
    in_block = False
    for line in text.splitlines():
        if "<!-- BEGIN AUTOGEN:" in line:
            in_block = True
        if not in_block:
            outside.append(line)
        if "<!-- END AUTOGEN:" in line:
            in_block = False
    return outside


def check_no_handwritten_controlled_fences(repo_root: Path) -> List[str]:
    """受控区外禁止出现可复制的完整 Scalim 示例信号。"""
    readme = repo_root / "README.md"
    if not readme.is_file():
        return ["缺少 README.md"]
    outside = "\n".join(_strip_autogen_blocks(_read(readme)))
    forbidden = (
        "ScalimEngine(",
        "DemandIr.from_irs(",
        "from scalim.execution.engine import ScalimEngine",
        'loader: "myapp.loaders:load_orders',
        "loader: {}".format(_REPO_LOADER_MODULE),
    )
    errors: List[str] = []
    for token in forbidden:
        if token in outside:
            errors.append("受控区外出现手写 README 示例信号: {!r}".format(token))
    return errors


def check_readme_examples_governance(repo_root: Path) -> List[str]:
    errors: List[str] = []
    errors.extend(check_readme_injection_drift(repo_root))
    errors.extend(check_no_handwritten_controlled_fences(repo_root))
    return errors
