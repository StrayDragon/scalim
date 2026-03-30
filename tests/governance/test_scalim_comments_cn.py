import subprocess
import sys
from pathlib import Path

from tests.support.pathing import repo_root as _repo_root


def test_scalim_docstrings_and_comments_are_chinese() -> None:
    repo_root = _repo_root()
    script = repo_root / "scripts" / "check-comments-cn.py"

    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(repo_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
