import importlib.util
import sys
from pathlib import Path

from tests.support.pathing import repo_root as _repo_root


def _load_script_module():
    repo_root = _repo_root()
    script_path = repo_root / "scripts" / "check-top-level-pyright-pragmas.py"
    module_name = "check_top_level_pyright_pragmas_for_tests"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_scan_top_level_pyright_pragmas_uses_real_file_header_and_tracks_misplaced(tmp_path) -> None:
    module = _load_script_module()

    _write_file(
        tmp_path / "src/scalim/ok_simple.py",
        "# pyright: strict\nx = 1\n",
    )
    _write_file(
        tmp_path / "src/scalim/ok_deep_header.py",
        "#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\n\n# generated file\n# another comment\n\n# pyright: strict\nx = 1\n",
    )
    _write_file(
        tmp_path / "src/scalim/bad_after_docstring.py",
        '"""module docstring"""\n# pyright: strict\nx = 1\n',
    )
    _write_file(
        tmp_path / "src/scalim/bad_after_import.py",
        "from __future__ import annotations\n# pyright: strict\nx = 1\n",
    )
    _write_file(
        tmp_path / "src/scalim/bad_indented.py",
        "    # pyright: strict\nx = 1\n",
    )
    _write_file(
        tmp_path / "src/scalim/inline_ignore_only.py",
        "from typing import Any  # pyright: ignore[reportUnusedImport]\nx = 1\n",
    )

    found, misplaced = module._scan_top_level_pyright_files(tmp_path)

    assert found == {
        "src/scalim/ok_deep_header.py",
        "src/scalim/ok_simple.py",
    }
    assert {path: [(location.line, location.column) for location in locations] for path, locations in misplaced.items()} == {
        "src/scalim/bad_after_docstring.py": [(2, 0)],
        "src/scalim/bad_after_import.py": [(2, 0)],
        "src/scalim/bad_indented.py": [(1, 4)],
    }


def test_main_strict_top_level_mode_rejects_misplaced_pragmas(tmp_path, capsys) -> None:
    module = _load_script_module()

    _write_file(
        tmp_path / "src/scalim/bad_after_docstring.py",
        '"""module docstring"""\n# pyright: strict\nx = 1\n',
    )
    _write_file(
        tmp_path / "scripts/top-level-pyright-pragmas.txt",
        "# 当前允许保留顶层 `# pyright:` pragma 的文件清单\n\n",
    )

    original_file = module.__file__
    try:
        module.__file__ = str(tmp_path / "scripts" / "check-top-level-pyright-pragmas.py")
        return_code = module.main(["--strict-top-level"])
    finally:
        module.__file__ = original_file

    captured = capsys.readouterr()
    assert return_code == 1
    assert "src/scalim/bad_after_docstring.py:2:1" in captured.err
    assert "严格顶层规则" in captured.err


def test_scan_type_checking_class_methods_only_flags_class_local_conditional_methods(tmp_path) -> None:
    module = _load_script_module()

    _write_file(
        tmp_path / "src/scalim/ok_module_level.py",
        "from typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n    from typing import Dict\n\nclass Good:\n    def run(self) -> None:\n        pass\n",
    )
    _write_file(
        tmp_path / "src/scalim/ok_class_without_methods.py",
        "from typing import TYPE_CHECKING\n\nclass Good:\n    if TYPE_CHECKING:\n        Alias = int\n",
    )
    _write_file(
        tmp_path / "src/scalim/bad_name.py",
        "from typing import TYPE_CHECKING\n\nclass Bad:\n    if TYPE_CHECKING:\n        def _ensure(self) -> None:\n            ...\n",
    )
    _write_file(
        tmp_path / "src/scalim/bad_attr.py",
        "import typing\n\nclass AlsoBad:\n    if typing.TYPE_CHECKING:\n        @staticmethod\n        def build() -> str:\n            ...\n",
    )

    violations = module._scan_type_checking_class_methods(tmp_path)

    assert {
        path: [(item.line, item.column, item.class_name, item.method_name) for item in items] for path, items in violations.items()
    } == {
        "src/scalim/bad_attr.py": [(6, 8, "AlsoBad", "build")],
        "src/scalim/bad_name.py": [(5, 8, "Bad", "_ensure")],
    }


def test_main_rejects_conditional_methods_inside_classes(tmp_path, capsys) -> None:
    module = _load_script_module()

    _write_file(
        tmp_path / "src/scalim/bad.py",
        "from typing import TYPE_CHECKING\n\nclass Bad:\n    if TYPE_CHECKING:\n        def x(self) -> None:\n            ...\n",
    )
    _write_file(
        tmp_path / "scripts/top-level-pyright-pragmas.txt",
        "# 当前允许保留顶层 `# pyright:` pragma 的文件清单\n\n",
    )

    original_file = module.__file__
    try:
        module.__file__ = str(tmp_path / "scripts" / "check-top-level-pyright-pragmas.py")
        return_code = module.main(["--strict-top-level"])
    finally:
        module.__file__ = original_file

    captured = capsys.readouterr()
    assert return_code == 1
    assert "src/scalim/bad.py:5:9" in captured.err
    assert "类=Bad 方法=x" in captured.err
    assert "ABC" in captured.err
