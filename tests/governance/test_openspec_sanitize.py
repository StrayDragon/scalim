import os
import shutil
import subprocess
import sys
from pathlib import Path

from tests.support.pathing import repo_root as _repo_root


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _subprocess_env(**overrides: str) -> dict:
    env = os.environ.copy()
    for key, value in overrides.items():
        if value is None:
            env.pop(key, None)
            continue
        env[key] = value
    return env


def _prepare_repo_fixture(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    scripts_root = repo_root / "scripts"
    openspec_root = repo_root / "openspec"
    source_repo_root = _repo_root()

    scripts_root.mkdir(parents=True, exist_ok=True)
    openspec_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_repo_root / "scripts" / "sanitize.py", scripts_root / "sanitize.py")
    shutil.copy2(source_repo_root / "openspec" / "sanitize_rules.yaml", openspec_root / "sanitize_rules.yaml")
    return repo_root


def test_sanitize_apply_rewrites_only_example_secret_tokens(tmp_path: Path) -> None:
    repo_root = _prepare_repo_fixture(tmp_path)
    openspec_root = repo_root / "openspec"
    sample = openspec_root / "sample.md"
    _write(
        sample,
        "\n".join(
            [
                "Path: /home/alice/Projects/acme/private/report.md",
                "Dir: with_alpha_reimpl",
                "App: demo_admin",
                'api_key: "secret-value"',
                "Use --token cli-secret for debug",
                "- token: `inline-secret`",
                "CLI: scalim-cli",
                "Source: src/scalim/runtime.py",
                "Import: from scalim.runtime import run",
                "Module: scalim.runtime.entrypoints",
                "Title: Scalim overview",
                "Package: scalim",
                "",
            ]
        ),
    )

    proc = subprocess.run(
        [sys.executable, str(repo_root / "scripts" / "sanitize.py"), "--apply", "--root", str(openspec_root), "--no-local-rules"],
        cwd=str(repo_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr

    text = sample.read_text(encoding="utf-8")
    assert 'api_key: "API_KEY_PLACEHOLDER"' in text
    assert "--token TOKEN_PLACEHOLDER" in text
    assert "`TOKEN_PLACEHOLDER`" in text
    assert "CLI: scalim-cli" in text
    assert "Source: src/scalim/runtime.py" in text
    assert "Import: from scalim.runtime import run" in text
    assert "Module: scalim.runtime.entrypoints" in text
    assert "Title: Scalim overview" in text
    assert "Package: scalim" in text

    assert "/home/alice/Projects/acme/private/report.md" in text
    assert "with_alpha_reimpl" in text
    assert "demo_admin" in text


def test_sanitize_prefers_target_root_rules_over_parent_rules(tmp_path: Path) -> None:
    repo_root = _prepare_repo_fixture(tmp_path)
    openspec_root = repo_root / "openspec"
    nested_root = openspec_root / "nested"
    nested_root.mkdir(parents=True, exist_ok=True)
    _write(
        nested_root / "sanitize_rules.yaml",
        "\n".join(
            [
                "version: 1",
                "rules:",
                "  - name: nested_token",
                '    pattern: "\\\\bnested-cli\\\\b"',
                '    replace: "NESTED_CLI"',
                "",
            ]
        ),
    )
    sample = nested_root / "sample.md"
    _write(sample, "Nested: nested-cli\nParent: scalim-cli\n")

    proc = subprocess.run(
        [sys.executable, str(repo_root / "scripts" / "sanitize.py"), "--apply", "--root", str(nested_root), "--no-local-rules"],
        cwd=str(repo_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr

    text = sample.read_text(encoding="utf-8")
    assert "NESTED_CLI" in text
    assert "scalim-cli" in text
    assert str(nested_root / "sanitize_rules.yaml") in proc.stdout
    assert str(openspec_root / "sanitize_rules.yaml") not in proc.stdout


def test_sanitize_auto_loads_local_rules_and_skips_rewriting_them(tmp_path: Path) -> None:
    repo_root = _prepare_repo_fixture(tmp_path)
    openspec_root = repo_root / "openspec"
    local_rules = openspec_root / "sanitize_rules.local.yaml"
    _write(
        local_rules,
        "\n".join(
            [
                "version: 1",
                "rules:",
                "  - name: private_vendor_name",
                '    pattern: "\\\\bSecretVendor\\\\b"',
                '    replace: "COMPANY_NAME"',
                "  - name: private_home_path",
                '    pattern: "/home/alice/work/private/"',
                '    replace: "REPO_ROOT/"',
                "",
            ]
        ),
    )
    sample = openspec_root / "notes.md"
    _write(sample, "Vendor: SecretVendor\nPath: /home/alice/work/private/note.md\n")

    proc = subprocess.run(
        [sys.executable, str(repo_root / "scripts" / "sanitize.py"), "--apply", "--root", str(openspec_root)],
        cwd=str(repo_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr

    text = sample.read_text(encoding="utf-8")
    assert "SecretVendor" not in text
    assert "COMPANY_NAME" in text
    assert "REPO_ROOT/note.md" in text
    assert "private_vendor_name" in proc.stdout
    assert "private_home_path" in proc.stdout
    assert "SecretVendor" in local_rules.read_text(encoding="utf-8")


def test_sanitize_warns_when_local_rules_missing(tmp_path: Path) -> None:
    repo_root = _prepare_repo_fixture(tmp_path)
    openspec_root = repo_root / "openspec"
    sample = openspec_root / "notes.md"
    _write(sample, "CLI: scalim-cli\n")

    proc = subprocess.run(
        [sys.executable, str(repo_root / "scripts" / "sanitize.py"), "--check", "--root", str(openspec_root)],
        cwd=str(repo_root),
        env=_subprocess_env(CI=None),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "sanitize_rules.local.yaml" in proc.stderr
    assert "仅应用公共规则" in proc.stderr


def test_sanitize_skips_missing_local_rules_warning_when_ci_enabled(tmp_path: Path) -> None:
    repo_root = _prepare_repo_fixture(tmp_path)
    openspec_root = repo_root / "openspec"
    sample = openspec_root / "notes.md"
    _write(sample, "CLI: scalim-cli\n")

    proc = subprocess.run(
        [sys.executable, str(repo_root / "scripts" / "sanitize.py"), "--check", "--root", str(openspec_root)],
        cwd=str(repo_root),
        env=_subprocess_env(CI="true"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "sanitize_rules.local.yaml" not in proc.stderr
    assert "仅应用公共规则" not in proc.stderr


def test_sanitize_still_warns_when_ci_value_is_falsey(tmp_path: Path) -> None:
    repo_root = _prepare_repo_fixture(tmp_path)
    openspec_root = repo_root / "openspec"
    sample = openspec_root / "notes.md"
    _write(sample, "CLI: scalim-cli\n")

    proc = subprocess.run(
        [sys.executable, str(repo_root / "scripts" / "sanitize.py"), "--check", "--root", str(openspec_root)],
        cwd=str(repo_root),
        env=_subprocess_env(CI="false"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "sanitize_rules.local.yaml" in proc.stderr
    assert "仅应用公共规则" in proc.stderr
