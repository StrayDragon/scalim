import argparse
import difflib
import os
import sys
import tempfile
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

try:
    import scalim_misc.yaml_schema_generator as _yaml_schema_generator
except Exception as exc:  # noqa: BLE001
    _yaml_schema_generator = None  # type: ignore[assignment]
    _yaml_schema_generator_import_error: Optional[Exception] = exc
else:
    _yaml_schema_generator_import_error = None


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _diff(a: str, b: str, a_name: str, b_name: str) -> str:
    return "\n".join(
        difflib.unified_diff(
            a.splitlines(),
            b.splitlines(),
            fromfile=a_name,
            tofile=b_name,
            lineterm="",
        )
    )


def _check_exact(path: Path, expected: str) -> Tuple[bool, str]:
    got = _read_text(path)
    if got == expected:
        return True, ""
    return False, _diff(got, expected, str(path), str(path) + " (expected)")


def _is_ci_env() -> bool:
    value = str(os.environ.get("CI") or "").strip().lower()
    return value not in ("", "0", "false", "no")


def _ensure_yaml_schema_generator_available() -> bool:
    if _yaml_schema_generator is not None:
        return True

    msg = (
        "[提示] 缺少开发依赖 `scalim-misc`: `YAML DSL` 的 `JSON Schema` 生成器不可用. "
        "修复建议: 安装开发依赖,或确保工作区包含 `scalim-misc`(例如 `uv sync --group dev`). "
        "原始错误: {}".format(_yaml_schema_generator_import_error)
    )
    if _is_ci_env():
        print(msg, file=sys.stderr)
        print("[错误] `CI` 环境必须启用 `YAML DSL` 的 `JSON Schema` 生成器; 当前检测到 `scalim-misc` 不可用.", file=sys.stderr)
        return False
    print(msg, file=sys.stderr)
    return False


def main(argv: Optional[Iterable[str]] = None) -> int:
    p = argparse.ArgumentParser(description="生成 YAML DSL schema (`*.gen.json`) 并提供漂移检查.")
    p.add_argument("--check", action="store_true", help="仅检查漂移,不写入文件.")
    args = p.parse_args(list(argv) if argv is not None else None)

    if not _ensure_yaml_schema_generator_available():
        return 1

    repo_root = Path(__file__).resolve().parents[1]
    schema_dir = repo_root / "src" / "scalim" / "dsl" / "yaml_dsl" / "schema"
    demand_path = schema_dir / "demand.gen.json"
    workflow_path = schema_dir / "workflow.gen.json"
    scalim_yaml_path = schema_dir / "scalim_yaml.gen.json"

    if not args.check:
        schema_dir.mkdir(parents=True, exist_ok=True)
        assert _yaml_schema_generator is not None
        _yaml_schema_generator.write_demand_schema(demand_path)
        _yaml_schema_generator.write_workflow_schema(workflow_path)
        _yaml_schema_generator.write_scalim_yaml_schema(scalim_yaml_path)
        return 0

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_schema_dir = Path(tmpdir)
        tmp_demand = tmp_schema_dir / "demand.gen.json"
        tmp_workflow = tmp_schema_dir / "workflow.gen.json"
        tmp_scalim_yaml = tmp_schema_dir / "scalim_yaml.gen.json"
        assert _yaml_schema_generator is not None
        _yaml_schema_generator.write_demand_schema(tmp_demand)
        _yaml_schema_generator.write_workflow_schema(tmp_workflow)
        _yaml_schema_generator.write_scalim_yaml_schema(tmp_scalim_yaml)

        expected = [
            (demand_path, tmp_demand.read_text(encoding="utf-8")),
            (workflow_path, tmp_workflow.read_text(encoding="utf-8")),
            (scalim_yaml_path, tmp_scalim_yaml.read_text(encoding="utf-8")),
        ]

    failed: List[Tuple[Path, str]] = []
    for path, expected_text in expected:
        ok, diff = _check_exact(path, expected_text)
        if not ok:
            failed.append((path, diff or "(diff unavailable)"))

    if failed:
        print("检测到 YAML DSL `schema` 漂移:")
        for path, diff in failed:
            print("\n--- {}".format(str(path)))
            print(diff)
        print("\n修复: 运行 `just gen-yaml-dsl-schema`")
        return 1

    print("通过: YAML DSL `schema` 一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
