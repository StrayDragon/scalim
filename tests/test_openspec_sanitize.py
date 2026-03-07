import shutil
import subprocess
import sys
from pathlib import Path


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _prepare_repo_fixture(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    scripts_root = repo_root / "scripts"
    openspec_root = repo_root / "openspec"
    source_repo_root = Path(__file__).resolve().parents[1]

    scripts_root.mkdir(parents=True, exist_ok=True)
    openspec_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_repo_root / "scripts" / "sanitize.py", scripts_root / "sanitize.py")
    shutil.copy2(source_repo_root / "openspec" / "sanitize_rules.yaml", openspec_root / "sanitize_rules.yaml")
    return repo_root


def test_sanitize_apply_rewrites_only_narrow_public_patterns(tmp_path: Path) -> None:
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
    assert "PROJECT_CLI_NAME" in text
    assert "src/IMPL_ROOT/runtime.py" in text
    assert "from IMPL_ROOT.runtime import run" in text
    assert "IMPL_ROOT.runtime.entrypoints" in text
    assert "PROJECT_NAME overview" in text
    assert "Package: PROJECT_DIST_NAME" in text

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
