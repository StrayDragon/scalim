import importlib.util
import sys
from pathlib import Path

from tests.support.pathing import repo_root as _repo_root


def _load_script_module():
    repo_root = _repo_root()
    script_path = repo_root / "scripts" / "check-notebook-cells-native.py"
    module_name = "check_notebook_cells_native_for_tests"
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


def _run(module, tmp_path, capsys):
    code = module.main(["--root", str(tmp_path), "--check"])
    captured = capsys.readouterr()
    return code, captured


def test_r1113_flags_run_delegation_from_support_module(tmp_path, capsys) -> None:
    module = _load_script_module()

    _write(
        tmp_path / "notebooks/marimo/suite/chapters/ch010_x.py",
        "\n".join(
            [
                "import marimo",
                "app = marimo.App(width='full')",
                "",
                "@app.cell",
                "def _():",
                "    from notebooks.marimo.suite.support.compare import run_compare",
                "    summary = run_compare()",
                "    return (run_compare, summary)",
            ]
        ),
    )

    code, captured = _run(module, tmp_path, capsys)

    assert code == 1
    assert "[r1113]" in captured.err
    assert "run_compare" in captured.err


def test_r1113_ignores_run_chapter_and_non_restricted_sources(tmp_path, capsys) -> None:
    module = _load_script_module()

    _write(
        tmp_path / "notebooks/marimo/suite/chapters/ch010_x.py",
        "\n".join(
            [
                "import marimo",
                "app = marimo.App(width='full')",
                "",
                "@app.cell",
                "def _():",
                "    from scalim.dsl.yaml_dsl import run as run_yaml",
                "    _ = run_yaml",
                "    return (run_yaml,)",
                "",
                "def run_chapter():",
                "    outputs, defs = app.run()",
                "    return defs['chapter_result']",
            ]
        ),
    )

    code, captured = _run(module, tmp_path, capsys)

    assert code == 0, captured.err


def test_r1113_pragma_allowlist_suppresses(tmp_path, capsys) -> None:
    module = _load_script_module()

    _write(
        tmp_path / "notebooks/marimo/suite/chapters/ch010_x.py",
        "\n".join(
            [
                "# pragma: allow-cells-native-run-delegation",
                "import marimo",
                "app = marimo.App(width='full')",
                "",
                "@app.cell",
                "def _():",
                "    from notebooks.marimo.suite.support.compare import run_compare",
                "    _ = run_compare",
                "    return (run_compare,)",
            ]
        ),
    )

    code, _ = _run(module, tmp_path, capsys)

    assert code == 0


def test_r1114_flags_details_literal_without_expected_key(tmp_path, capsys) -> None:
    module = _load_script_module()

    _write(
        tmp_path / "notebooks/marimo/suite/chapters/ch020_x.py",
        "\n".join(
            [
                "import marimo",
                "app = marimo.App(width='full')",
                "",
                "@app.cell",
                "def _():",
                "    from scalim_misc.notebook_support.chapter_result import make_chapter_result",
                "    chapter_result = make_chapter_result(",
                "        passed=True,",
                "        summary='ok',",
                "        details={'rows': 3, 'checks': {}},",
                "    )",
                "    return (chapter_result,)",
            ]
        ),
    )

    code, captured = _run(module, tmp_path, capsys)

    assert code == 1
    assert "[r1114]" in captured.err


def test_r1114_accepts_expected_key_and_non_literal_details(tmp_path, capsys) -> None:
    module = _load_script_module()

    _write(
        tmp_path / "notebooks/marimo/suite/chapters/ch020_x.py",
        "\n".join(
            [
                "import marimo",
                "app = marimo.App(width='full')",
                "",
                "@app.cell",
                "def _():",
                "    from scalim_misc.notebook_support.chapter_result import make_chapter_result",
                "    summary = {'rows': 3}",
                "    chapter_result_a = make_chapter_result(",
                "        passed=True,",
                "        summary='ok',",
                "        details={'expected_rows': 3, 'checks': {}},",
                "    )",
                "    chapter_result_b = make_chapter_result(passed=True, summary='ok', details=summary)",
                "    return (chapter_result_a, chapter_result_b)",
            ]
        ),
    )

    code, _ = _run(module, tmp_path, capsys)

    assert code == 0


def test_scanner_passes_on_current_repo_tree() -> None:
    module = _load_script_module()
    repo_root = _repo_root()

    code = module.main(["--root", str(repo_root)])

    assert code == 0
