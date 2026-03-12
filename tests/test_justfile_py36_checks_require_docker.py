from pathlib import Path


def _extract_recipe(justfile_text: str, name: str) -> str:
    lines = justfile_text.splitlines()
    start = None
    header = "{}:".format(name)
    for idx, line in enumerate(lines):
        if line == header:
            start = idx + 1
            break
    if start is None:
        raise AssertionError("recipe not found: {}".format(name))

    body_lines = []
    for line in lines[start:]:
        if line and not line.startswith((" ", "\t")):
            break
        body_lines.append(line)
    return "\n".join(body_lines)


def test_py36_compat_checks_require_docker() -> None:
    justfile = Path("justfile").read_text(encoding="utf-8")

    compat_body = _extract_recipe(justfile, "py36-compat-check")
    assert "docker run" in compat_body
    assert "check-py36-syntax.py" not in compat_body
    assert "fallback" not in compat_body

    typingext_body = _extract_recipe(justfile, "py36-typingext-check")
    assert "docker run" in typingext_body
    assert "bash /repo/scripts/check-py36-typingext-docker.sh" in typingext_body
    assert "bash scripts/check-py36-typingext-docker.sh" not in typingext_body
    assert "fallback" not in typingext_body
