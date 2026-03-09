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
    source_repo_root = Path(__file__).resolve().parents[1]

    scripts_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_repo_root / "scripts" / "check-py-doc-language.py", scripts_root / "check-py-doc-language.py")
    return repo_root


def test_check_py_doc_language_reports_english_comments_without_ignore(tmp_path: Path) -> None:
    repo_root = _prepare_repo_fixture(tmp_path)
    sample = repo_root / "scripts" / "sample_module.py"
    _write(sample, "# English comment should be reported\n")

    proc = subprocess.run(
        [sys.executable, str(repo_root / "scripts" / "check-py-doc-language.py")],
        cwd=str(repo_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    assert proc.returncode == 1
    assert "sample_module.py" in proc.stderr
    assert "English comment should be reported" in proc.stderr


def test_check_py_doc_language_supports_force_en_comments_and_docstrings(tmp_path: Path) -> None:
    repo_root = _prepare_repo_fixture(tmp_path)
    sample = repo_root / "scripts" / "sample_module.py"
    _write(
        sample,
        "\n".join(
            [
                "# force-en",
                "# English comment may stay here",
                "",
                "def demo() -> None:",
                "    # force-en",
                '    """English docstring may stay here."""',
                "    pass",
                "",
                "# force-en",
                '"English string expr may stay here."',
                "",
            ]
        ),
    )

    proc = subprocess.run(
        [sys.executable, str(repo_root / "scripts" / "check-py-doc-language.py")],
        cwd=str(repo_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
