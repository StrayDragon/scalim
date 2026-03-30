import importlib.util
import sys
from pathlib import Path

from tests.support.pathing import repo_root as _repo_root


def _load_script_module():
    repo_root = _repo_root()
    script_path = repo_root / "scripts" / "check-no-cover.py"
    module_name = "check_no_cover_for_tests"
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


def test_no_cover_scanner_requires_explicit_allow_reason(tmp_path) -> None:
    module = _load_script_module()

    sample = tmp_path / "src/scalim/sample.py"
    _write(
        sample,
        "\n".join(
            [
                "# pragma: allow-no-cover abstract fallback branch",
                "if flag:  # pragma: no cover",
                "    pass",
                "",
                "if other:  # pragma: no cover",
                "    pass",
                "",
            ]
        )
        + "\n",
    )

    hits = module.scan_repo(repo_root=tmp_path, rel_roots=(Path("src/scalim"),))

    assert [(hit.status, hit.allow_reason) for hit in hits] == [
        ("allow", "abstract fallback branch"),
        ("block", ""),
    ]


def test_no_cover_scanner_supports_file_level_allow(tmp_path) -> None:
    module = _load_script_module()

    sample = tmp_path / "src/scalim/sample.py"
    _write(
        sample,
        "\n".join(
            [
                "# pragma: allow-no-cover-file generated compatibility wrapper",
                "",
                "def build() -> None:",
                "    return None  # pragma: no cover",
                "",
            ]
        )
        + "\n",
    )

    hits = module.scan_repo(repo_root=tmp_path, rel_roots=(Path("src/scalim"),))

    assert [(hit.status, hit.allow_reason) for hit in hits] == [
        ("allow", "generated compatibility wrapper"),
    ]


def test_no_cover_check_mode_fails_on_unallowed_hits(tmp_path, capsys) -> None:
    module = _load_script_module()

    _write(tmp_path / "src/scalim/sample.py", "if flag:  # pragma: no cover\n    pass\n")

    original_file = module.__file__
    try:
        module.__file__ = str(tmp_path / "scripts" / "check-no-cover.py")
        return_code = module.main(["src/scalim", "--check", "--no-artifacts"])
    finally:
        module.__file__ = original_file

    captured = capsys.readouterr()
    assert return_code == 1
    assert "sample.py" in captured.out
