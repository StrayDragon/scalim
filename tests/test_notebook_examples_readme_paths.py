from pathlib import Path

_NOTEBOOK_ROOT_DIR = Path("notebooks/marimo")
_NOTEBOOK_DEMO_DIR = _NOTEBOOK_ROOT_DIR / "demo_big_data_report"
_NOTEBOOK_PUBLIC_API_DIR = _NOTEBOOK_ROOT_DIR / "example_public_api"
_PKG_DEMO_DIR = Path("packages/scalim-misc/src/scalim_misc/demo_big_data_report")
_PKG_PUBLIC_API_DIR = Path("packages/scalim-misc/src/scalim_misc/examples/public_api")


def test_demo_directory_contains_unified_examples() -> None:
    assert (_NOTEBOOK_DEMO_DIR / "demo_main.py").exists()
    assert (_NOTEBOOK_ROOT_DIR / "run_examples.py").exists()
    assert (_NOTEBOOK_DEMO_DIR / "by_yaml_dsl" / "ecommerce_report.yaml").exists()
    assert (_NOTEBOOK_PUBLIC_API_DIR / "index.py").exists()
    assert (_PKG_DEMO_DIR / "chapters").is_dir()
    assert _PKG_PUBLIC_API_DIR.is_dir()
