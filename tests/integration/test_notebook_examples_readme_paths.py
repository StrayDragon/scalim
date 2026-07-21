from pathlib import Path

_NOTEBOOK_ROOT_DIR = Path("notebooks/marimo")
_NOTEBOOK_DEMO_DIR = _NOTEBOOK_ROOT_DIR / "demo_big_data_report"
_NOTEBOOK_DEMO_CHAPTERS_OF_YAML_DSL_DIR = _NOTEBOOK_DEMO_DIR / "chapters_of_yaml_dsl"
_NOTEBOOK_DEMO_CHAPTERS_OF_IR_DIR = _NOTEBOOK_DEMO_DIR / "chapters_of_ir"


def test_demo_directory_contains_unified_examples() -> None:
    assert not (_NOTEBOOK_ROOT_DIR / "index.py").exists()
    assert (_NOTEBOOK_DEMO_DIR / "demo_main.py").exists()
    assert _NOTEBOOK_DEMO_CHAPTERS_OF_YAML_DSL_DIR.is_dir()
    assert _NOTEBOOK_DEMO_CHAPTERS_OF_IR_DIR.is_dir()
    assert not (_NOTEBOOK_ROOT_DIR / "run_examples.py").exists()
    assert (_NOTEBOOK_DEMO_CHAPTERS_OF_YAML_DSL_DIR / "declared_yaml_dsl" / "ecommerce_report.yaml").exists()
    assert not (_NOTEBOOK_ROOT_DIR / "example_public_api").exists()
    assert (_NOTEBOOK_ROOT_DIR / "example_public_api_suite").is_dir()
    assert (_NOTEBOOK_ROOT_DIR / "example_hooks_events_scenarios").is_dir()
    assert (_NOTEBOOK_ROOT_DIR / "example_hooks_events_scenarios" / "demo_main.py").exists()

    from notebooks.marimo.demo_big_data_report.chapters_of_ir.registry import iter_chapters as iter_ir_chapters
    from notebooks.marimo.demo_big_data_report.chapters_of_yaml_dsl.registry import iter_chapters as iter_yaml_dsl_chapters

    expected_chapter_ids = list(iter_yaml_dsl_chapters()) + list(iter_ir_chapters())
    names = [p.name for p in _NOTEBOOK_DEMO_CHAPTERS_OF_YAML_DSL_DIR.glob("*.py")]
    names.extend([p.name for p in _NOTEBOOK_DEMO_CHAPTERS_OF_IR_DIR.glob("*.py")])
    for chapter_id in expected_chapter_ids:
        assert any(name.endswith("{}{}.py".format("_", chapter_id)) or name == "{}.py".format(chapter_id) for name in names), chapter_id
