"""Quiet contract for serious check gates: pass silent; failures still report."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from tests.support.pathing import repo_root as _repo_root


def _load_script(name: str):
    repo_root = _repo_root()
    script_path = repo_root / "scripts" / name
    module_name = "quiet_contract_{}".format(name.replace("-", "_").replace(".", "_"))
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


def test_api_surface_quiet_pass_and_tmp_failure(tmp_path, capsys) -> None:
    module = _load_script("check-api-surface-governance.py")

    ok_root = tmp_path / "ok"
    _write(ok_root / "pkg.py", "__all__ = ()\n")
    assert module.main(["--root", str(ok_root), "--check", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""

    bad_root = tmp_path / "bad"
    _write(bad_root / "_internal_mod.py", "X = 1\n")
    assert module.main(["--root", str(bad_root), "--check", "--quiet"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "[错误]" in captured.err


def test_no_print_quiet_pass_and_tmp_failure(tmp_path, monkeypatch, capsys) -> None:
    module = _load_script("check-no-print.py")

    fake_root = tmp_path / "repo"
    _write(fake_root / "src/scalim/ok.py", "x = 1\n")
    _write(fake_root / "scripts" / "check-no-print.py", "# placeholder\n")
    monkeypatch.setattr(module, "__file__", str(fake_root / "scripts" / "check-no-print.py"))

    assert module.main(["--check", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""

    _write(fake_root / "src/scalim/bad.py", "print(1)\n")
    assert module.main(["--check", "--quiet"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "[错误]" in captured.err
    assert "bad.py" in captured.err


def test_noqa_c901_quiet_pass_and_tmp_failure(tmp_path, monkeypatch, capsys) -> None:
    module = _load_script("check-noqa-c901.py")

    fake_root = tmp_path / "repo"
    _write(fake_root / "src/scalim/ok.py", "def f():\n    return 1\n")
    _write(fake_root / "scripts" / "check-noqa-c901.py", "# placeholder\n")
    monkeypatch.setattr(module, "__file__", str(fake_root / "scripts" / "check-noqa-c901.py"))

    assert module.main(["--check", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""

    _write(fake_root / "src/scalim/bad.py", "def f():  # noqa: C901\n    return 1\n")
    assert module.main(["--check", "--quiet"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "[错误]" in captured.err
    assert "bad.py" in captured.err


def test_export_api_quiet_pass_and_tmp_list_failure(tmp_path, monkeypatch) -> None:
    import subprocess

    root = tmp_path / "src" / "scalim"
    _write(root / "ok.py", "__all__ = ()\n")
    repo = _repo_root()
    cmd = [
        "uv",
        "run",
        str(repo / "scripts" / "check-export-api-must-tuple.py"),
        "--root",
        "src/scalim",
        "--check",
        "--strict",
        "--quiet",
    ]
    pass_run = subprocess.run(cmd, cwd=str(tmp_path), capture_output=True, text=True, check=False)
    assert pass_run.returncode == 0
    assert pass_run.stdout == ""
    assert pass_run.stderr == ""

    _write(root / "bad.py", '__all__ = ["x"]\n')
    fail_run = subprocess.run(cmd, cwd=str(tmp_path), capture_output=True, text=True, check=False)
    assert fail_run.returncode == 1
    assert fail_run.stdout == ""
    assert "[错误]" in fail_run.stderr
    assert "bad.py" in fail_run.stderr


def test_user_material_quiet_pass_and_tmp_failure(tmp_path, capsys) -> None:
    module = _load_script("check-user-material-import-boundaries.py")

    docs = tmp_path / "docs" / "doc"
    notebooks = tmp_path / "notebooks" / "marimo"
    skills = tmp_path / "agentdev" / "skills"
    docs.mkdir(parents=True)
    notebooks.mkdir(parents=True)
    skills.mkdir(parents=True)

    assert (
        module.main(
            [
                "--root",
                str(tmp_path),
                "--docs-root",
                "docs/doc",
                "--notebooks-root",
                "notebooks/marimo",
                "--skills-root",
                "agentdev/skills",
                "--check",
                "--quiet",
            ]
        )
        == 0
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""

    _write(docs / "bad.md", "from scalim.events._catalog import get_event_catalog\n")
    assert (
        module.main(
            [
                "--root",
                str(tmp_path),
                "--docs-root",
                "docs/doc",
                "--notebooks-root",
                "notebooks/marimo",
                "--skills-root",
                "agentdev/skills",
                "--check",
                "--quiet",
            ]
        )
        == 1
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "[错误]" in captured.err


def test_module_size_quiet_pass_and_tmp_over_limit(tmp_path, monkeypatch, capsys) -> None:
    module = _load_script("check-module-size.py")

    fake_root = tmp_path / "repo"
    hotspot = fake_root / "src" / "scalim" / "hot.py"
    _write(hotspot, "a\nb\nc\n")
    _write(fake_root / "scripts" / "check-module-size.py", "# placeholder\n")
    monkeypatch.setattr(module, "__file__", str(fake_root / "scripts" / "check-module-size.py"))
    monkeypatch.setattr(module, "_HOTSPOT_LIMITS", {"src/scalim/hot.py": 100})

    assert module.main(["--check", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""

    monkeypatch.setattr(module, "_HOTSPOT_LIMITS", {"src/scalim/hot.py": 1})
    assert module.main(["--check", "--quiet"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "[错误]" in captured.err
    assert "hot.py" in captured.err


def test_dispatch_map_quiet_pass_and_monkeypatched_gap(monkeypatch, capsys) -> None:
    module = _load_script("check-dispatch-map-completeness.py")

    assert module.main(["--check", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""

    real_catalog = module._collect_event_types()

    def _inflated_catalog():
        return real_catalog | {"synthetic_missing_event_for_quiet_test"}

    monkeypatch.setattr(module, "_collect_event_types", _inflated_catalog)
    monkeypatch.setattr(module, "_is_workflow_event", lambda _name: False)

    assert module.main(["--check", "--quiet"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "[错误]" in captured.err
    assert "synthetic_missing_event_for_quiet_test" in captured.err


def test_object_type_quiet_pass_and_tmp_block(tmp_path, monkeypatch, capsys) -> None:
    module = _load_script("check-object-type.py")

    fake_root = tmp_path / "repo"
    _write(fake_root / "src/scalim/ok.py", "def f(x: int) -> int:\n    return x\n")
    _write(fake_root / "scripts" / "check-object-type.py", "# placeholder\n")
    monkeypatch.setattr(module, "__file__", str(fake_root / "scripts" / "check-object-type.py"))

    assert module.main(["src/scalim", "--check", "--quiet", "--no-artifacts"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""

    _write(fake_root / "src/scalim/bad.py", "def f(x: object) -> object:\n    return x\n")
    assert module.main(["src/scalim", "--check", "--quiet", "--no-artifacts"]) == 1
    captured = capsys.readouterr()
    assert "block=" in captured.out
    assert "bad.py" in captured.out


def test_monkeypatch_policy_quiet_pass_and_tmp_failure(tmp_path, capsys) -> None:
    module = _load_script("check-monkeypatch-policy.py")

    _write(
        tmp_path / "tests/workflow/test_ok.py",
        "\n".join(
            [
                "def test_x(monkeypatch):",
                "    obj = object()",
                "    monkeypatch.setattr(obj, 'public', 1)",
                "",
            ]
        ),
    )
    assert module.main(["--root", str(tmp_path), "--check", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""

    _write(
        tmp_path / "tests/workflow/test_bad.py",
        "\n".join(
            [
                "def test_x(monkeypatch):",
                "    obj = object()",
                "    monkeypatch.setattr(obj, '_secret', 1)",
                "",
            ]
        ),
    )
    assert module.main(["--root", str(tmp_path), "--check", "--quiet"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "[错误]" in captured.err


def test_tests_domain_suites_quiet_pass_and_tmp_failure(tmp_path, capsys) -> None:
    module = _load_script("check-tests-domain-suites.py")

    for name in (
        "bench",
        "execution",
        "fixtures",
        "governance",
        "integration",
        "ob",
        "planning",
        "public_api",
        "sinks",
        "support",
        "workflow",
        "yaml_dsl",
    ):
        (tmp_path / "tests" / name).mkdir(parents=True, exist_ok=True)

    assert module.main(["--root", str(tmp_path), "--check", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""

    _write(tmp_path / "tests/test_smoke.py", "def test_smoke():\n    assert True\n")
    assert module.main(["--root", str(tmp_path), "--check", "--quiet"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "[错误]" in captured.err
