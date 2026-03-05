from pathlib import Path

from scalim.dsl.by_yaml.schema_dsl.builder import write_demand_schema


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    schema_dir = repo_root / "src" / "scalim" / "dsl" / "by_yaml" / "schema"
    output_path = schema_dir / "demand.gen.json"

    write_demand_schema(output_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
