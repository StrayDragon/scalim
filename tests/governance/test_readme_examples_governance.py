from pathlib import Path

from notebooks.marimo.example_readme_suite.support.inject import (
    BEGIN_MIN_PYTHON,
    END_MIN_PYTHON,
    _snippet_blocks,
    check_no_handwritten_controlled_fences,
    check_readme_examples_governance,
)
from notebooks.marimo.example_readme_suite.support.render_chart import (
    ASSET_COMPARE,
    ASSET_EB_MATRIX,
    ASSET_EB_MATRIX_TIME,
    ASSET_EB_SWEEP,
    ASSET_EB_SWEEP_TIME,
    ASSET_SCENARIOS,
    expected_assets,
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


def test_yaml_quickstart_is_a_generated_user_loader_projection() -> None:
    block = _snippet_blocks()["min_yaml"]

    assert block.startswith("```yaml\n")
    assert 'loader: "myapp.loaders:load_orders"' in block
    assert 'loader: "myapp.loaders:load_payments"' in block
    assert "notebooks.marimo.example_readme_suite.support.min_yaml_loaders" not in block
    assert "support/min_yaml_example.yaml" in block
    assert "support/min_yaml.py" in block


def test_readme_chart_assets_use_local_rss_terms() -> None:
    assets = {path: body for path, body in expected_assets()}

    assert set(assets) == {ASSET_COMPARE, ASSET_SCENARIOS, ASSET_EB_SWEEP, ASSET_EB_SWEEP_TIME, ASSET_EB_MATRIX, ASSET_EB_MATRIX_TIME}
    assert "本地内存变化" in assets[ASSET_COMPARE]
    assert "RSS" in assets[ASSET_COMPARE]
    for body in assets.values():
        assert "Relative peak RSS" not in body
        assert "Approx. RSS reduction" not in body
