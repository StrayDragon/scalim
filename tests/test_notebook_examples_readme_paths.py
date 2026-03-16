from pathlib import Path

_NOTEBOOK_ROOT_DIR = Path("notebooks/marimo")
_NOTEBOOK_DEMO_DIR = _NOTEBOOK_ROOT_DIR / "demo_big_data_report"
_NOTEBOOK_DEMO_CHAPTERS_DIR = _NOTEBOOK_DEMO_DIR / "chapters"


def test_demo_directory_contains_unified_examples() -> None:
    assert (_NOTEBOOK_ROOT_DIR / "index.py").exists()
    assert (_NOTEBOOK_DEMO_DIR / "demo_main.py").exists()
    assert _NOTEBOOK_DEMO_CHAPTERS_DIR.is_dir()
    assert (_NOTEBOOK_ROOT_DIR / "run_examples.py").exists()
    assert (_NOTEBOOK_DEMO_DIR / "by_yaml_dsl" / "ecommerce_report.yaml").exists()
    assert not (_NOTEBOOK_ROOT_DIR / "example_public_api").exists()

    from notebooks.marimo.demo_big_data_report.chapters.registry import iter_chapters

    expected_chapter_ids = list(iter_chapters())
    names = [p.name for p in _NOTEBOOK_DEMO_CHAPTERS_DIR.glob("*.py")]
    for chapter_id in expected_chapter_ids:
        assert any(name.endswith("{}{}.py".format("_", chapter_id)) or name == "{}.py".format(chapter_id) for name in names), chapter_id
