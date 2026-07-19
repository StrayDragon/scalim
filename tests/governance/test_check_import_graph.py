import importlib.util
import sys
from pathlib import Path

from tests.support.pathing import repo_root as _repo_root


def _load_script_module():
    repo_root = _repo_root()
    script_path = repo_root / "scripts" / "check-import-graph.py"
    module_name = "check_import_graph_for_tests"
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


def test_import_graph_check_fails_on_cycle(tmp_path, capsys) -> None:
    module = _load_script_module()

    _write(tmp_path / "src/scalim/__init__.py", "")
    _write(tmp_path / "src/scalim/a.py", "import scalim.b\n")
    _write(tmp_path / "src/scalim/b.py", "import scalim.a\n")

    return_code = module.main(["--root", str(tmp_path), "--check"])
    captured = capsys.readouterr()

    assert return_code == 1
    assert "导入环" in captured.err
    assert "scalim.a" in captured.err
    assert "scalim.b" in captured.err


def test_import_graph_check_fails_on_function_local_import(tmp_path, capsys) -> None:
    module = _load_script_module()

    _write(tmp_path / "src/scalim/__init__.py", "")
    _write(
        tmp_path / "src/scalim/sample.py",
        "\n".join(
            [
                "def build() -> int:",
                "    import os",
                "    return 1",
                "",
            ]
        ),
    )

    return_code = module.main(["--root", str(tmp_path), "--check"])
    captured = capsys.readouterr()

    assert return_code == 1
    assert "函数内导入" in captured.err
    assert "sample.py" in captured.err


def test_import_graph_check_passes_on_acyclic_graph(tmp_path, capsys) -> None:
    module = _load_script_module()

    _write(tmp_path / "src/scalim/__init__.py", "")
    _write(tmp_path / "src/scalim/a.py", "import scalim.b\n")
    _write(tmp_path / "src/scalim/b.py", "VALUE = 1\n")

    return_code = module.main(["--root", str(tmp_path), "--check"])
    captured = capsys.readouterr()

    assert return_code == 0
    assert "[通过]" in captured.out


def test_import_graph_quiet_silences_pass_stdout(tmp_path, capsys) -> None:
    module = _load_script_module()

    _write(tmp_path / "src/scalim/__init__.py", "")
    _write(tmp_path / "src/scalim/a.py", "VALUE = 1\n")

    return_code = module.main(["--root", str(tmp_path), "--check", "--quiet"])
    captured = capsys.readouterr()

    assert return_code == 0
    assert captured.out == ""
    assert captured.err == ""


def test_import_graph_quiet_still_reports_failures_on_stderr(tmp_path, capsys) -> None:
    module = _load_script_module()

    _write(tmp_path / "src/scalim/__init__.py", "")
    _write(tmp_path / "src/scalim/a.py", "import scalim.b\n")
    _write(tmp_path / "src/scalim/b.py", "import scalim.a\n")

    return_code = module.main(["--root", str(tmp_path), "--check", "--quiet"])
    captured = capsys.readouterr()

    assert return_code == 1
    assert captured.out == ""
    assert "导入环" in captured.err
