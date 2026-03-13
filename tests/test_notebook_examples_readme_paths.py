from pathlib import Path

_NOTEBOOK_DEMO_DIR = Path("notebooks/marimo/demo_big_data_report")
_PKG_DEMO_DIR = Path("packages/scalim-misc/src/scalim_misc/demo_big_data_report")


def test_demo_directory_contains_unified_examples() -> None:
    assert (_NOTEBOOK_DEMO_DIR / "demo_main.py").exists()
    assert (_NOTEBOOK_DEMO_DIR / "run_examples.py").exists()
    assert (_NOTEBOOK_DEMO_DIR / "by_yaml_dsl" / "ecommerce_report.yaml").exists()
    assert (_PKG_DEMO_DIR / "chapters").is_dir()
