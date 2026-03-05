import re
from pathlib import Path

import pytest


_README = Path("notebooks/marimo/examples/README.md")
_DEMO_DIR = Path("notebooks/marimo/examples/demo_big_data_report")


def _extract_demo_paths(readme_text: str):
    pattern = re.compile(r"`(?P<path>(?:demo_[a-z0-9_]+\.py|by_yaml_dsl/))`")
    results = []
    for match in pattern.finditer(readme_text):
        value = match.group("path")
        if value == "by_yaml_dsl/":
            results.append("demo_big_data_report/by_yaml_dsl/")
            continue
        results.append("demo_big_data_report/{}".format(value))
    return results


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
    paths = _extract_demo_paths(content)

    assert paths, "README 未提取到 demo 引用"
    _validate_readme_demo_paths(paths)


@pytest.mark.parametrize("broken", ["demo_big_data_report/demo_b0_all_sinks.py"])
def test_readme_demo_paths_reports_missing(broken: str) -> None:
    with pytest.raises(AssertionError) as exc:
        _validate_readme_demo_paths([broken])

    message = str(exc.value)
    assert "README 引用了不存在的 demo 路径" in message
    assert broken in message


def test_demo_directory_contains_unified_examples() -> None:
    demo_files = sorted(path.name for path in _DEMO_DIR.glob("demo_*.py"))
    assert "demo_b0_sinks_unified.py" in demo_files
    assert "demo_c0_transforms_unified.py" in demo_files
    assert "demo_d0_hooks_unified.py" in demo_files
