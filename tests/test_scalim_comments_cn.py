import subprocess
import sys
from pathlib import Path


def test_scalim_docstrings_and_comments_are_chinese() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    script = repo_root / "scripts" / "check-comments-cn.py"

    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(repo_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
