import ast
from pathlib import Path


def test_monkeypatch_policy_forbids_private_and_global_import_patching() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    tests_dir = repo_root / "tests"

    violations = []

    for path in sorted(tests_dir.rglob("*.py")):
        if path.name == Path(__file__).name:
            continue

        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute):
                continue

            # 仅对 `pytest` 的 `monkeypatch` 夹具执行该策略.
            if not (isinstance(func.value, ast.Name) and func.value.id == "monkeypatch" and func.attr == "setattr"):
                continue

            if len(node.args) < 2:
                continue

            target_expr = node.args[0]
            name_expr = node.args[1]

            if not (isinstance(name_expr, ast.Constant) and isinstance(name_expr.value, str)):
                continue

            attr_name = name_expr.value

            rel_path = path.relative_to(repo_root)
            loc = "%s:%s" % (rel_path.as_posix(), getattr(node, "lineno", "?"))

            if attr_name.startswith("_"):
                violations.append("%s: monkeypatch.setattr(..., %r, ...) patches a private name" % (loc, attr_name))
                continue

            if attr_name == "__import__" and isinstance(target_expr, ast.Name) and target_expr.id == "builtins":
                violations.append("%s: monkeypatch.setattr(builtins, '__import__', ...) patches global import" % loc)
                continue

            if attr_name == "import_module" and isinstance(target_expr, ast.Name) and target_expr.id == "importlib":
                violations.append("%s: monkeypatch.setattr(importlib, 'import_module', ...) patches global import" % loc)
                continue

    assert not violations, "Banned monkeypatch patterns found:\n- " + "\n- ".join(violations)
