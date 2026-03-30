import importlib.util
import sys
from pathlib import Path

from tests.support.pathing import repo_root as _repo_root


def _load_script_module():
    repo_root = _repo_root()
    script_path = repo_root / "scripts" / "check-cast-usage.py"
    module_name = "check_cast_usage_for_tests"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_cast_usage_scanner_detects_import_styles_and_allow_markers(tmp_path) -> None:
    module = _load_script_module()

    sample = tmp_path / "src/scalim/sample.py"
    _write(
        sample,
        "\n".join(
            [
                "from typing import cast as typing_cast",
                "import typing_extensions as te",
                "",
                "value = typing_cast(str, object())",
                "other = te.cast(int, object())  # pragma: allow-cast compatibility boundary",
                "",
            ]
        )
        + "\n",
    )

    hits = module.scan_repo(repo_root=tmp_path, rel_roots=(Path("src/scalim"),))

    assert [(hit.source_summary, hit.status, hit.allow_reason) for hit in hits] == [
        ("typing.cast", "block", ""),
        ("typing_extensions.cast", "allow", "compatibility boundary"),
    ]


def test_cast_usage_scanner_ignores_shadowed_name(tmp_path) -> None:
    module = _load_script_module()

    sample = tmp_path / "src/scalim/sample.py"
    _write(
        sample,
        "\n".join(
            [
                "from typing import cast",
                "",
                "def build() -> int:",
                "    cast = lambda value, _obj: value",
                "    return cast(1, object())",
                "",
            ]
        )
        + "\n",
    )

    hits = module.scan_repo(repo_root=tmp_path, rel_roots=(Path("src/scalim"),))

    assert hits == []


def test_cast_usage_check_mode_fails_on_unallowed_hits(tmp_path, capsys) -> None:
    module = _load_script_module()

    _write(tmp_path / "src/scalim/sample.py", "from typing import cast\nvalue = cast(str, object())\n")

    original_file = module.__file__
    try:
        module.__file__ = str(tmp_path / "scripts" / "check-cast-usage.py")
        return_code = module.main(["src/scalim", "--check", "--no-artifacts"])
    finally:
        module.__file__ = original_file

    captured = capsys.readouterr()
    assert return_code == 1
    assert "sample.py" in captured.out
