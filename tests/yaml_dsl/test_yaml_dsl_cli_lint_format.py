import argparse
import json
from pathlib import Path

import scalim_cli.yaml_dsl as yaml_dsl


def _lint_args(*paths: Path, fix: bool, json_output: bool) -> argparse.Namespace:
    return argparse.Namespace(
        paths=list(paths),
        fix=fix,
        json=json_output,
    )


def _format_args(*paths: Path, check: bool, diff: bool) -> argparse.Namespace:
    return argparse.Namespace(
        paths=list(paths),
        check=check,
        diff=diff,
    )


def test_yaml_dsl_format_unquotes_safe_references_and_is_idempotent(tmp_path: Path) -> None:
    yaml_path = tmp_path / "demo.yaml"
    yaml_path.write_text(
        """
fields:
  x:
    loader: "pkg.mod:load_x"
    compute: "order_id"
    call_by: "pkg.mod:fn(a=a)"
    retry:
      should_retry: "false"
""".lstrip(),
        encoding="utf-8",
    )

    code = yaml_dsl._run_format(_format_args(yaml_path, check=False, diff=False))
    assert code == 0

    formatted = yaml_path.read_text(encoding="utf-8")
    assert "loader: pkg.mod:load_x" in formatted
    assert "compute: order_id" in formatted
    assert "call_by: pkg.mod:fn(a=a)" in formatted
    assert 'should_retry: "false"' in formatted

    code2 = yaml_dsl._run_format(_format_args(yaml_path, check=False, diff=False))
    assert code2 == 0
    assert yaml_path.read_text(encoding="utf-8") == formatted


def test_yaml_dsl_format_check_and_diff_do_not_write_and_return_nonzero_when_changes_exist(tmp_path: Path, capsys) -> None:
    yaml_path = tmp_path / "demo.yaml"
    yaml_path.write_text(
        """
fields:
  x:
    compute: "order_id"
""".lstrip(),
        encoding="utf-8",
    )

    original = yaml_path.read_text(encoding="utf-8")
    code = yaml_dsl._run_format(_format_args(yaml_path, check=True, diff=False))
    assert code == 1
    assert yaml_path.read_text(encoding="utf-8") == original

    code2 = yaml_dsl._run_format(_format_args(yaml_path, check=False, diff=True))
    assert code2 == 1
    assert yaml_path.read_text(encoding="utf-8") == original

    out = capsys.readouterr().out
    assert "---" in out
    assert "+++" in out


def test_yaml_dsl_lint_json_output_contains_codes_and_ranges(tmp_path: Path, capsys) -> None:
    yaml_path = tmp_path / "demo.yaml"
    yaml_path.write_text(
        """
fields:
  x:
    compute: "order_id"
""".lstrip(),
        encoding="utf-8",
    )

    code = yaml_dsl._run_lint(_lint_args(yaml_path, fix=False, json_output=True))
    assert code == 1

    payload = json.loads(capsys.readouterr().out)
    issues = payload["issues"]
    assert any(item["code"] == "YDL001" for item in issues)
    first = issues[0]
    assert "range" in first
    assert "start" in first["range"]
    assert "end" in first["range"]


def test_yaml_dsl_lint_fix_removes_unnecessary_quotes(tmp_path: Path) -> None:
    yaml_path = tmp_path / "demo.yaml"
    yaml_path.write_text(
        """
fields:
  x:
    compute: "order_id"
""".lstrip(),
        encoding="utf-8",
    )

    code = yaml_dsl._run_lint(_lint_args(yaml_path, fix=True, json_output=False))
    assert code == 0

    fixed = yaml_path.read_text(encoding="utf-8")
    assert "compute: order_id" in fixed
    assert 'compute: "order_id"' not in fixed


def test_yaml_dsl_format_directory_discovery_excludes_tmp_and_dist(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()

    good = root / "good.yaml"
    good.write_text(
        """
fields:
  x:
    compute: "order_id"
""".lstrip(),
        encoding="utf-8",
    )

    excluded_dir = root / ".tmp"
    excluded_dir.mkdir()
    excluded = excluded_dir / "excluded.yaml"
    excluded.write_text(
        """
fields:
  x:
    compute: "order_id"
""".lstrip(),
        encoding="utf-8",
    )

    dist_dir = root / "dist"
    dist_dir.mkdir()
    dist_file = dist_dir / "dist.yaml"
    dist_file.write_text(
        """
fields:
  x:
    compute: "order_id"
""".lstrip(),
        encoding="utf-8",
    )

    code = yaml_dsl._run_format(_format_args(root, check=False, diff=False))
    assert code == 0

    assert "compute: order_id" in good.read_text(encoding="utf-8")
    assert 'compute: "order_id"' in excluded.read_text(encoding="utf-8")
    assert 'compute: "order_id"' in dist_file.read_text(encoding="utf-8")
