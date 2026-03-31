from pathlib import Path

from scalim.dsl.by_yaml._internal.config_parsing.validator import ConfigValidator


def _validator() -> ConfigValidator:
    repo_root = Path(__file__).resolve().parents[2]
    schema_path = repo_root / "src" / "scalim" / "dsl" / "by_yaml" / "schema" / "demand.gen.json"
    return ConfigValidator(schema_path=str(schema_path))


def test_config_validator_allows_import_only_output_target_shape() -> None:
    report = _validator().validate_report(
        {
            "name": "demo",
            "main_source": {
                "source_id": "orders",
                "loader": "tests.fixtures.mock_loaders.mock_loader",
            },
            "sources": {},
            "outputs": [{"$import": "common.outputs"}],
        },
        strict_unknown_fields=True,
        enable_jsonschema_validation=True,
    )

    assert report.errors() == []


def test_validator_sources_skip_import_and_cover_key_edge_cases() -> None:
    report = _validator().validate_report(
        {
            "name": "demo",
            "main_source": {
                "source_id": "orders",
                "loader": "",
                "retry": {"should_retry": "   "},
            },
            "sources": {
                "$import": "fragments.yaml",
                "s_key_none": {"loader": "tests.fixtures.mock_loaders.mock_loader", "key": None},
                "s_key_empty_list": {"loader": "tests.fixtures.mock_loaders.mock_loader", "key": []},
                "s_key_non_str": {"loader": "tests.fixtures.mock_loaders.mock_loader", "key": [1]},
                "s_key_blank": {"loader": "tests.fixtures.mock_loaders.mock_loader", "key": [""]},
                "s_key_bad_pat_list": {"loader": "tests.fixtures.mock_loaders.mock_loader", "key": ["bad-id"]},
                "s_key_bad_pat_str": {"loader": "tests.fixtures.mock_loaders.mock_loader", "key": "bad-id"},
            },
        },
        strict_unknown_fields=False,
        enable_jsonschema_validation=False,
    )

    errors = report.errors()
    messages = [issue.message for issue in errors]
    paths = [issue.path for issue in errors]

    assert all(not str(path).startswith("sources.$import") for path in paths)
    assert any("main_source.loader must not be empty" in msg for msg in messages)
    assert any("main_source.retry.should_retry" in msg and "must not be empty when provided" in msg for msg in messages)
    assert any("sources.s_key_none.key must be a non-empty field_id or field_id list" in msg for msg in messages)
    assert any("sources.s_key_empty_list.key must not be empty" in msg for msg in messages)
    assert any("sources.s_key_non_str.key.0 must be a string" in msg for msg in messages)
    assert any("sources.s_key_blank.key.0 must not be empty" in msg for msg in messages)
    assert any("sources.s_key_bad_pat_list.key.0 must match field_id pattern" in msg for msg in messages)
    assert any("sources.s_key_bad_pat_str.key must match field_id pattern" in msg for msg in messages)
