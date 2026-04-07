import argparse
import json
from pathlib import Path
from typing import Iterable, Set

import jsonschema
import pytest

import scalim.cli.yaml_dsl as yaml_dsl_cli
from scalim.dsl.yaml_dsl.schema_dsl.builder import build_demand_schema


def _args(path: Path) -> argparse.Namespace:
    return argparse.Namespace(
        yaml_file=path,
        schema=None,
        json=True,
        verbose=False,
    )


def _fixture_text(name: str) -> str:
    fixtures_dir = Path(__file__).resolve().parents[1] / "fixtures"
    return (fixtures_dir / name).read_text(encoding="utf-8")


def _write_fixture(tmp_path: Path, name: str) -> Path:
    target = tmp_path / name
    target.write_text(_fixture_text(name), encoding="utf-8")
    return target


def _run_validate(path: Path, capsys) -> dict:
    assert yaml_dsl_cli._run_validate(_args(path)) == 1
    return json.loads(capsys.readouterr().out)


def _run_schema_validate(path: Path, capsys) -> dict:
    assert yaml_dsl_cli._run_schema_validate(_args(path)) == 1
    return json.loads(capsys.readouterr().out)


def _assert_has_any_path(payload: dict, prefixes: Iterable[str]) -> None:
    expected: Set[str] = {str(p) for p in prefixes if str(p)}
    errors = payload.get("errors") or []
    paths = [item.get("path") or "" for item in errors if isinstance(item, dict)]
    assert any(any(str(p).startswith(prefix) for prefix in expected) for p in paths), {
        "expected_prefixes": sorted(expected),
        "paths": paths,
    }


@pytest.mark.parametrize(
    ("fixture", "validate_prefixes", "schema_prefixes"),
    [
        ("yaml_dsl_invalid_main_source_source_id.yaml", ["main_source.source_id"], ["main_source.source_id"]),
        ("yaml_dsl_invalid_sources_key.yaml", ["sources.123-invalid"], ["sources"]),
        ("yaml_dsl_empty_source_loader.yaml", ["sources.customers.loader"], ["sources.customers.loader"]),
        ("yaml_dsl_empty_source_key.yaml", ["sources.customers.key"], ["sources.customers.key"]),
        ("yaml_dsl_retry_enabled_missing_should_retry.yaml", ["retry"], ["retry"]),
        ("yaml_dsl_outputs_container_streaming_false.yaml", ["outputs.0.container"], ["outputs.0.container"]),
        ("yaml_dsl_detail_output_missing_fields.yaml", ["outputs.0.fields"], ["outputs.0"]),
    ],
)
def test_cli_validate_and_schema_validate_fail_fast_on_known_runtime_only_shapes(
    tmp_path: Path,
    capsys,
    fixture: str,
    validate_prefixes: Iterable[str],
    schema_prefixes: Iterable[str],
) -> None:
    yaml_path = _write_fixture(tmp_path, fixture)

    validate_payload = _run_validate(yaml_path, capsys)
    assert validate_payload["ok"] is False
    _assert_has_any_path(validate_payload, validate_prefixes)

    schema_payload = _run_schema_validate(yaml_path, capsys)
    assert schema_payload["ok"] is False
    _assert_has_any_path(schema_payload, schema_prefixes)


def test_schema_rejects_import_only_output_target_shape() -> None:
    schema = build_demand_schema()

    data = {
        "name": "demo",
        "main_source": {
            "source_id": "orders",
            "loader": "tests.fixtures.mock_loaders.mock_loader",
        },
        "outputs": [
            {
                "$import": "common.outputs",
            }
        ],
    }

    with pytest.raises(jsonschema.exceptions.ValidationError):
        jsonschema.Draft7Validator(schema).validate(data)


def test_schema_validate_accepts_normalize_on_none_skip_for_index_by_key() -> None:
    schema = build_demand_schema()
    data = {
        "name": "demo",
        "main_source": {
            "source_id": "orders",
            "loader": "tests.fixtures.mock_loaders.mock_loader",
        },
        "sources": {
            "recommends": {
                "loader": "tests.fixtures.mock_loaders.mock_loader",
                "key": "order_id",
                "normalize": {
                    "kind": "index_by_key",
                    "key_field": "order_id",
                    "on_none": "skip",
                },
            }
        },
    }
    jsonschema.Draft7Validator(schema).validate(data)


def test_schema_validate_rejects_normalize_on_none_for_non_index_by_key() -> None:
    schema = build_demand_schema()
    data = {
        "name": "demo",
        "main_source": {
            "source_id": "orders",
            "loader": "tests.fixtures.mock_loaders.mock_loader",
        },
        "sources": {
            "recommends": {
                "loader": "tests.fixtures.mock_loaders.mock_loader",
                "key": "order_id",
                "normalize": {
                    "kind": "project_fields",
                    "fields": {"id": {"from_key": True}},
                    "on_none": "skip",
                },
            }
        },
    }
    with pytest.raises(jsonschema.exceptions.ValidationError):
        jsonschema.Draft7Validator(schema).validate(data)
