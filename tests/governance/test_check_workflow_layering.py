import importlib.util
import sys
from pathlib import Path

from tests.support.pathing import repo_root as _repo_root


def _load_script_module():
    repo_root = _repo_root()
    script_path = repo_root / "scripts" / "check-workflow-layering.py"
    module_name = "check_workflow_layering_for_tests"
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


def test_workflow_layering_check_fails_on_dsl_import(tmp_path, capsys) -> None:
    module = _load_script_module()

    _write(tmp_path / "src/scalim/workflow/__init__.py", "")
    _write(tmp_path / "src/scalim/workflow/execute.py", "import scalim.dsl.yaml_dsl\n")

    return_code = module.main(["--root", str(tmp_path), "--check"])
    captured = capsys.readouterr()

    assert return_code == 1
    assert "import 'scalim.dsl.yaml_dsl'" in captured.err


def test_workflow_layering_check_fails_on_dynamic_import(tmp_path, capsys) -> None:
    module = _load_script_module()

    _write(tmp_path / "src/scalim/workflow/__init__.py", "")
    _write(
        tmp_path / "src/scalim/workflow/execute.py",
        "\n".join(
            [
                "import importlib",
                "importlib.import_module('scalim.dsl.yaml_dsl')",
                "",
            ]
        ),
    )

    return_code = module.main(["--root", str(tmp_path), "--check"])
    captured = capsys.readouterr()

    assert return_code == 1
    assert "dynamic import" in captured.err


def test_workflow_layering_check_fails_on_workflow_runtime_module_in_yaml_dsl_runtime(tmp_path, capsys) -> None:
    module = _load_script_module()

    _write(tmp_path / "src/scalim/workflow/__init__.py", "")
    _write(tmp_path / "src/scalim/dsl/yaml_dsl/runtime/workflow_bad.py", "# sentinel\n")

    return_code = module.main(["--root", str(tmp_path), "--check"])
    captured = capsys.readouterr()

    assert return_code == 1
    assert "workflow_bad.py" in captured.err


def test_workflow_layering_check_passes(tmp_path, capsys) -> None:
    module = _load_script_module()

    _write(tmp_path / "src/scalim/workflow/__init__.py", "")
    _write(tmp_path / "src/scalim/workflow/execute.py", "import scalim.workflow\n")
    _write(tmp_path / "src/scalim/dsl/yaml_dsl/runtime/entrypoints.py", "# ok\n")

    return_code = module.main(["--root", str(tmp_path), "--check"])
    captured = capsys.readouterr()

    assert return_code == 0
    assert "[通过]" in captured.out
