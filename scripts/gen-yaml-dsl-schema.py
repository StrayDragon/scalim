import argparse
import difflib
import tempfile
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from scalim.dsl.yaml_dsl.schema_dsl.builder import write_demand_schema, write_scalim_yaml_schema, write_workflow_schema


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


def main(argv: Optional[Iterable[str]] = None) -> int:
    p = argparse.ArgumentParser(description="生成 YAML DSL schema (`*.gen.json`) 并提供漂移检查.")
    p.add_argument("--check", action="store_true", help="仅检查漂移,不写入文件.")
    args = p.parse_args(list(argv) if argv is not None else None)

    repo_root = Path(__file__).resolve().parents[1]
    schema_dir = repo_root / "src" / "scalim" / "dsl" / "yaml_dsl" / "schema"
    demand_path = schema_dir / "demand.gen.json"
    workflow_path = schema_dir / "workflow.gen.json"
    scalim_yaml_path = schema_dir / "scalim_yaml.gen.json"

    if not args.check:
        schema_dir.mkdir(parents=True, exist_ok=True)
        write_demand_schema(demand_path)
        write_workflow_schema(workflow_path)
        write_scalim_yaml_schema(scalim_yaml_path)
        return 0

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_schema_dir = Path(tmpdir)
        tmp_demand = tmp_schema_dir / "demand.gen.json"
        tmp_workflow = tmp_schema_dir / "workflow.gen.json"
        tmp_scalim_yaml = tmp_schema_dir / "scalim_yaml.gen.json"
        write_demand_schema(tmp_demand)
        write_workflow_schema(tmp_workflow)
        write_scalim_yaml_schema(tmp_scalim_yaml)

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
