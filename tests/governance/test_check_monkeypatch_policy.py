import importlib.util
import sys
from pathlib import Path

from tests.support.pathing import repo_root as _repo_root


def _load_script_module():
    repo_root = _repo_root()
    script_path = repo_root / "scripts" / "check-monkeypatch-policy.py"
    module_name = "check_monkeypatch_policy_for_tests"
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


def test_monkeypatch_policy_check_fails_on_private_patch(tmp_path, capsys) -> None:
    module = _load_script_module()

    _write(
        tmp_path / "tests/workflow/test_policy.py",
        "\n".join(
            [
                "def test_x(monkeypatch):",
                "    obj = object()",
                "    monkeypatch.setattr(obj, '_secret', 1)",
                "",
            ]
        ),
    )

    return_code = module.main(["--root", str(tmp_path), "--check"])
    captured = capsys.readouterr()

    assert return_code == 1
    assert "patches a private name" in captured.err


def test_monkeypatch_policy_check_fails_on_global_import_patch(tmp_path, capsys) -> None:
    module = _load_script_module()

    _write(
        tmp_path / "tests/workflow/test_policy.py",
        "\n".join(
            [
                "def test_x(monkeypatch):",
                "    monkeypatch.setattr(builtins, '__import__', lambda *a, **k: None)",
                "",
            ]
        ),
    )

    return_code = module.main(["--root", str(tmp_path), "--check"])
    captured = capsys.readouterr()

    assert return_code == 1
    assert "patches a private name" in captured.err


def test_monkeypatch_policy_check_fails_on_importlib_import_module_patch(tmp_path, capsys) -> None:
    module = _load_script_module()

    _write(
        tmp_path / "tests/workflow/test_policy.py",
        "\n".join(
            [
                "def test_x(monkeypatch):",
                "    monkeypatch.setattr(importlib, 'import_module', lambda *a, **k: None)",
                "",
            ]
        ),
    )

    return_code = module.main(["--root", str(tmp_path), "--check"])
    captured = capsys.readouterr()

    assert return_code == 1
    assert "patches global import" in captured.err


def test_monkeypatch_policy_check_passes_on_public_attr_patch(tmp_path, capsys) -> None:
    module = _load_script_module()

    _write(
        tmp_path / "tests/workflow/test_policy.py",
        "\n".join(
            [
                "def test_x(monkeypatch):",
                "    obj = object()",
                "    monkeypatch.setattr(obj, 'public', 1)",
                "",
            ]
        ),
    )

    return_code = module.main(["--root", str(tmp_path), "--check"])
    captured = capsys.readouterr()

    assert return_code == 0
    assert "[通过]" in captured.out
