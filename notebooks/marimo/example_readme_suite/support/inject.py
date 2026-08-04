"""生成 README 中的示例、图表，并检查生成结果是否被手改。"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from scalim_misc.markdown_inject import InjectBlockSpec, InjectBlockError, replace_markdown_injected_block

from notebooks.marimo.example_readme_suite.support.render_chart import (
    ASSET_COMPARE,
    ASSET_SCENARIOS,
    expected_assets,
)

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

_SUITE = "notebooks/marimo/example_readme_suite"
_MIN_YAML = Path(__file__).resolve().parent / "min_yaml_example.yaml"
_REPO_LOADER_MODULE = "notebooks.marimo.example_readme_suite.support.min_yaml_loaders"
_USER_LOADER_MODULE = "myapp.loaders"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _pointer_block(*, rel_path: str, note: str) -> str:
    lines = [
        "- 代码：[`{rel}`](./{rel})".format(rel=rel_path),
        "- {note}".format(note=note),
        "",
    ]
    return "\n".join(lines)


def _chart_block() -> str:
    lines = [
        "![本地内存变化对比：naive 和 Scalim]({})".format(ASSET_COMPARE.as_posix()),
        "",
        "![不同数据大小下的本地内存变化]({})".format(ASSET_SCENARIOS.as_posix()),
        "",
    ]
    return "\n".join(lines)


def _yaml_quickstart_block() -> str:
    source = _read(_MIN_YAML)
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
        "- 完整配置：[`support/min_yaml_example.yaml`](./{}/support/min_yaml_example.yaml)".format(_SUITE),
        "- 示例数据和运行脚本：[`support/min_yaml_loaders.py`](./{}/support/min_yaml_loaders.py) · "
        "[`support/min_yaml.py`](./{}/support/min_yaml.py)".format(_SUITE, _SUITE),
        "",
    ]
    return "\n".join(lines)


def _snippet_blocks() -> Dict[str, str]:
    gate = "在仓库中可用 `just examples` 运行，也可用 `just notebook` 打开"
    return {
        "min_python": _pointer_block(
            rel_path="{}/support/min_python.py".format(_SUITE),
            note="章节：`{}/chapters/ch010_min_python.py`；{}".format(_SUITE, gate),
        ),
        "min_yaml": _yaml_quickstart_block(),
        "naive": _pointer_block(
            rel_path="{}/support/naive_baseline.py".format(_SUITE),
            note="对比章节：`{}/chapters/ch030_memory_compare.py`；{}".format(_SUITE, gate),
        ),
        "scalim": _pointer_block(
            rel_path="{}/support/scalim_path.py".format(_SUITE),
            note="对比章节：`{}/chapters/ch030_memory_compare.py`；{}".format(_SUITE, gate),
        ),
        "chart": _chart_block(),
    }


def expected_readme_text(current: str) -> str:
    blocks = _snippet_blocks()
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
    updated = expected_readme_text(_read(path))
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
        expected = expected_readme_text(text)
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
        'loader: "examples.readme.min_yaml_loaders',
        'loader: "notebooks.marimo.example_readme_suite.support.min_yaml_loaders',
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
