import importlib.util
import sys
from pathlib import Path

from tests.support.pathing import repo_root as _repo_root


def _load_script_module():
    repo_root = _repo_root()
    script_path = repo_root / "scripts" / "check-tests-domain-suites.py"
    module_name = "check_tests_domain_suites_for_tests"
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


def _create_required_suites(tests_root: Path) -> None:
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
        (tests_root / name).mkdir(parents=True, exist_ok=True)


def test_tests_domain_suites_check_fails_on_missing_domain_dirs(tmp_path, capsys) -> None:
    module = _load_script_module()

    (tmp_path / "tests").mkdir(parents=True, exist_ok=True)

    return_code = module.main(["--root", str(tmp_path), "--check"])
    captured = capsys.readouterr()

    assert return_code == 1
    assert "缺少必要的领域套件目录" in captured.err


def test_tests_domain_suites_check_fails_on_root_test_file(tmp_path, capsys) -> None:
    module = _load_script_module()

    _create_required_suites(tmp_path / "tests")
    _write(tmp_path / "tests/test_smoke.py", "def test_smoke():\n    assert True\n")

    return_code = module.main(["--root", str(tmp_path), "--check"])
    captured = capsys.readouterr()

    assert return_code == 1
    assert "移入某个领域套件目录" in captured.err


def test_tests_domain_suites_check_fails_on_additional_pattern(tmp_path, capsys) -> None:
    module = _load_script_module()

    _create_required_suites(tmp_path / "tests")
    _write(tmp_path / "tests/workflow/test_topic_additional.py", "def test_x():\n    assert True\n")

    return_code = module.main(["--root", str(tmp_path), "--check"])
    captured = capsys.readouterr()

    assert return_code == 1
    assert "禁止 `*_additional`" in captured.err


def test_tests_domain_suites_check_fails_on_forbidden_tests_ref(tmp_path, capsys) -> None:
    module = _load_script_module()

    _create_required_suites(tmp_path / "tests")
    forbidden_ref = "tests" + ".bad_ref.mod:callable"
    _write(
        tmp_path / "tests/workflow/test_refs.py",
        "\n".join(
            [
                "VALUE = {!r}".format(forbidden_ref),
                "",
            ]
        ),
    )

    return_code = module.main(["--root", str(tmp_path), "--check"])
    captured = capsys.readouterr()

    assert return_code == 1
    assert ("tests" + ".bad_ref.mod") in captured.err


def test_tests_domain_suites_check_passes_on_allowed_fixture_refs(tmp_path, capsys) -> None:
    module = _load_script_module()

    _create_required_suites(tmp_path / "tests")
    _write(tmp_path / "tests/workflow/test_refs.py", "VALUE = 'tests.fixtures.mod:callable'\n")

    return_code = module.main(["--root", str(tmp_path), "--check"])
    captured = capsys.readouterr()

    assert return_code == 0
    assert "[通过]" in captured.out
