import re
from pathlib import Path


def test_notebook_support_has_no_marimo_imports() -> None:
    notebook_support_dir = Path("packages/scalim-misc/src/scalim_misc/notebook_support")
    assert notebook_support_dir.is_dir()

    import_pat = re.compile(r"^\s*(?:from|import)\s+marimo\b")
    offenders = []
    for path in sorted(notebook_support_dir.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if import_pat.search(line):
                offenders.append("{}:{}:{}".format(path, lineno, line.strip()))
                break

    assert not offenders, "unexpected marimo import in notebook_support:\n{}".format("\n".join(offenders))
