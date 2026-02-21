from pathlib import Path

import pytest


_README = Path("notebooks/marimo/examples/README.md")
_DEMO_DIR = Path("notebooks/marimo/examples/demo_big_data_report")
_TUTOR = _DEMO_DIR / "demo_tutor.py"


def _validate_readme_demo_paths(paths):
    missing = []
    for relative_path in paths:
        target = Path("notebooks/marimo/examples") / relative_path
        if not target.exists():
            missing.append(str(target))
    if missing:
        msg = "README 引用了不存在的 demo 路径: {}".format(", ".join(sorted(missing)))
        raise AssertionError(msg)


def test_readme_demo_paths_all_exist() -> None:
    content = _README.read_text(encoding="utf-8")
    assert "demo_tutor.py" in content
    paths = ["demo_big_data_report/demo_tutor.py"]

    _validate_readme_demo_paths(paths)
    assert _TUTOR.exists()


@pytest.mark.parametrize("broken", ["demo_big_data_report/demo_missing.py"])
def test_readme_demo_paths_reports_missing(broken: str) -> None:
    with pytest.raises(AssertionError) as exc:
        _validate_readme_demo_paths([broken])

    message = str(exc.value)
    assert "README 引用了不存在的 demo 路径" in message
    assert broken in message


def test_demo_directory_contains_unified_examples() -> None:
    demo_files = sorted(path.name for path in _DEMO_DIR.glob("demo_*.py"))
    assert demo_files == ["demo_tutor.py"]
