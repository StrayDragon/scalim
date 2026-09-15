from pathlib import Path

_NOTEBOOK_ROOT_DIR = Path("notebooks/marimo")
_NOTEBOOK_DEMO_DIR = _NOTEBOOK_ROOT_DIR / "demo_big_data_report"
_CHAPTERS_OF_YAML_DSL_DIR = _NOTEBOOK_DEMO_DIR / "chapters_of_yaml_dsl"
_CHAPTERS_OF_IR_DIR = _NOTEBOOK_DEMO_DIR / "chapters_of_ir"
_CHAPTERS_OF_SCENARIOS_DIR = _NOTEBOOK_DEMO_DIR / "chapters_of_scenarios"

# 单一用户心智: `notebooks/marimo/` 下只有主线套件目录 + `_templates` 模板目录.
_TRAILING_SUITE_DIRS = ("example_public_api_suite", "example_hooks_events_scenarios", "example_stage_scheduling_perf")


def _chapter_file_present(names: list[str], chapter_id: str) -> bool:
    """轨道内 `chapter_id` 可能省略 `chNNN_` 前缀, 因此同时允许全名与后缀匹配."""
    return "{}.py".format(chapter_id) in names or any(name.endswith("_{}.py".format(chapter_id)) for name in names)


def test_demo_directory_contains_unified_examples() -> None:
    assert not (_NOTEBOOK_ROOT_DIR / "index.py").exists()
    assert not (_NOTEBOOK_ROOT_DIR / "run_examples.py").exists()
    assert (_NOTEBOOK_DEMO_DIR / "demo_main.py").exists()
    assert _CHAPTERS_OF_YAML_DSL_DIR.is_dir()
    assert _CHAPTERS_OF_IR_DIR.is_dir()
    assert _CHAPTERS_OF_SCENARIOS_DIR.is_dir()
    assert (_CHAPTERS_OF_YAML_DSL_DIR / "declared_yaml_dsl" / "ecommerce_report.yaml").exists()
    assert not (_NOTEBOOK_ROOT_DIR / "example_public_api").exists()
    for suite_dir in _TRAILING_SUITE_DIRS:
        assert not (_NOTEBOOK_ROOT_DIR / suite_dir).exists(), suite_dir

    from notebooks.marimo.demo_big_data_report.chapters_of_ir.registry import iter_chapters as iter_ir_chapters
    from notebooks.marimo.demo_big_data_report.chapters_of_scenarios.registry import iter_chapters as iter_scenario_chapters
    from notebooks.marimo.demo_big_data_report.chapters_of_yaml_dsl.registry import iter_chapters as iter_yaml_dsl_chapters

    tracks = [
        (iter_yaml_dsl_chapters, _CHAPTERS_OF_YAML_DSL_DIR),
        (iter_ir_chapters, _CHAPTERS_OF_IR_DIR),
        (iter_scenario_chapters, _CHAPTERS_OF_SCENARIOS_DIR),
    ]
    total = 0
    for iter_chapters, chapter_dir in tracks:
        names = [p.name for p in chapter_dir.glob("*.py")]
        for chapter_id in iter_chapters():
            total += 1
            assert _chapter_file_present(names, chapter_id), chapter_id
    assert total == 52, total
