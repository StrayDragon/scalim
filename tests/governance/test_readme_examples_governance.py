from pathlib import Path

from scalim_misc.readme_charts_gen import (
    ASSET_COMPARE,
    ASSET_EB_MATRIX,
    ASSET_EB_MATRIX_TIME,
    ASSET_EB_SWEEP,
    ASSET_EB_SWEEP_TIME,
    ASSET_SCENARIOS,
    expected_assets,
)
from scalim_misc.readme_examples_gen import (
    BEGIN_MIN_PYTHON,
    END_MIN_PYTHON,
    _snippet_blocks,
    check_no_handwritten_controlled_fences,
    check_readme_examples_governance,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_readme_governance_fails_when_marker_missing(tmp_path: Path) -> None:
    _write(tmp_path / "README.md", "# hi\n")
    errors = check_readme_examples_governance(tmp_path)
    assert any("缺少必需标记" in item for item in errors)


def test_readme_governance_rejects_handwritten_engine_outside_autogen(tmp_path: Path) -> None:
    text = "\n".join(
        [
            "# demo",
            BEGIN_MIN_PYTHON,
            "```python",
            "print(1)",
            "```",
            END_MIN_PYTHON,
            "",
            "```python",
            "from scalim.execution.engine import ScalimEngine",
            "ScalimEngine(",
            "```",
            "",
        ]
    )
    _write(tmp_path / "README.md", text)
    errors = check_no_handwritten_controlled_fences(tmp_path)
    assert any("受控区外出现手写 README 示例信号" in item for item in errors)


def test_min_python_block_is_projected_from_mainline_chapter_cells() -> None:
    """README 最小示例的 Python 代码 = 主线 ch010 核心闭环 cells ①~④ 的投影(同一链路,无第二真相).

    ⑤/⑥ 对拍脚手架不入投影, 完整演示经章节链接给出。
    """
    block = _snippet_blocks()["min_python"]

    assert block.startswith("以下核心代码逐 cell 投影自主线章节 ch010")
    assert "```python" in block
    for token in (
        "MainSourceIr(source_id=",
        "DemandIr.from_irs(",
        "PlanBuilder(demand).build()",
        "ScalimEngine(",
        "engine.run(sink=sink)",
        "rows = list(sink.get_data())",
    ):
        assert token in block, token
    # ⑤/⑥ 对拍/断言 cell 不入投影(完整演示给章节链接)
    for token in ("expected_rows = [", "render_checks(checks)", "chapter_result = make_chapter_result"):
        assert token not in block, token
    # hide_code 叙事 cell 不入投影
    assert "mo.callout" not in block
    assert "chapters_of_ir/ch010_basics.py" in block
    assert "完整演示" in block


def test_yaml_quickstart_is_a_generated_user_loader_projection() -> None:
    block = _snippet_blocks()["min_yaml"]

    assert block.startswith("```yaml\n")
    assert "loader: myapp.loaders:load_orders" in block
    assert "loader: myapp.loaders:load_payments" in block
    assert "scalim_misc.demo_big_data_report.min_loaders" not in block
    assert "declared_yaml_dsl/min_report.yaml" in block
    assert "chapters_of_yaml_dsl/ch005_yaml_dsl_min.py" in block


def test_memory_compare_blocks_point_to_mainline_chapter() -> None:
    blocks = _snippet_blocks()

    for key in ("naive", "scalim"):
        assert "chapters_of_ir/ch020_memory_compare.py" in blocks[key]
    assert "naive 基线管线" in blocks["naive"]
    assert "scalim 窄字段管线" in blocks["scalim"]


def test_readme_chart_assets_use_local_rss_terms() -> None:
    assets = {path: body for path, body in expected_assets()}

    assert set(assets) == {ASSET_COMPARE, ASSET_SCENARIOS, ASSET_EB_SWEEP, ASSET_EB_SWEEP_TIME, ASSET_EB_MATRIX, ASSET_EB_MATRIX_TIME}
    assert "本地内存变化" in assets[ASSET_COMPARE]
    assert "RSS" in assets[ASSET_COMPARE]
    for body in assets.values():
        assert "Relative peak RSS" not in body
        assert "Approx. RSS reduction" not in body
