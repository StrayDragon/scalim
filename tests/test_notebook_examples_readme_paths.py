from pathlib import Path

_DEMO_DIR = Path("notebooks/marimo/demo_big_data_report")


def test_demo_directory_contains_unified_examples() -> None:
    assert (_DEMO_DIR / "demo_main.py").exists()
    assert (_DEMO_DIR / "run_examples.py").exists()
    assert (_DEMO_DIR / "chapters").is_dir()
    assert (_DEMO_DIR / "by_yaml_dsl" / "ecommerce_report.yaml").exists()
