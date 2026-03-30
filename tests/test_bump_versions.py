import subprocess
import sys
from pathlib import Path


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _repo_fixture(root: Path) -> None:
    _write(
        root / "pyproject.toml",
        '[project]\nname = "scalim"\nversion = "0.2.1"\n',
    )
    _write(
        root / "packages" / "scalim-benchlib" / "pyproject.toml",
        '[project]\nname = "scalim-benchlib"\nversion = "0.1.0"\n',
    )
    _write(
        root / "packages" / "scalim-misc" / "pyproject.toml",
        '[project]\nname = "scalim-misc"\nversion = "0.1.0"\n',
    )
    _write(root / "frontend" / "scalim-viz" / "package.json", '{\n  "name": "scalim-viz",\n  "version": "0.0.1",\n  "private": true\n}\n')


def test_bump_versions_dry_run_does_not_modify_files(tmp_path: Path) -> None:
    _repo_fixture(tmp_path)
    script = Path(__file__).resolve().parents[1] / "scripts" / "bump-versions.py"

    proc = subprocess.run(
        [sys.executable, str(script), "--root", str(tmp_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "dry-run" in proc.stdout
    assert 'version = "0.1.0"' in (tmp_path / "packages" / "scalim-benchlib" / "pyproject.toml").read_text(encoding="utf-8")
    assert '"version": "0.0.1"' in (tmp_path / "frontend" / "scalim-viz" / "package.json").read_text(encoding="utf-8")


def test_bump_versions_apply_updates_whitelisted_files(tmp_path: Path) -> None:
    _repo_fixture(tmp_path)
    script = Path(__file__).resolve().parents[1] / "scripts" / "bump-versions.py"

    proc = subprocess.run(
        [sys.executable, str(script), "--root", str(tmp_path), "--version", "0.3.0", "--apply"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert 'version = "0.3.0"' in (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "0.3.0"' in (tmp_path / "packages" / "scalim-benchlib" / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "0.3.0"' in (tmp_path / "packages" / "scalim-misc" / "pyproject.toml").read_text(encoding="utf-8")
    assert '"version": "0.3.0"' in (tmp_path / "frontend" / "scalim-viz" / "package.json").read_text(encoding="utf-8")


def test_bump_versions_rejects_invalid_version(tmp_path: Path) -> None:
    _repo_fixture(tmp_path)
    script = Path(__file__).resolve().parents[1] / "scripts" / "bump-versions.py"

    proc = subprocess.run(
        [sys.executable, str(script), "--root", str(tmp_path), "--version", "oops"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    assert proc.returncode == 2
    assert "无效版本" in proc.stderr
