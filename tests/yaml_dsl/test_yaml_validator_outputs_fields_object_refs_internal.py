import scalim.dsl.by_yaml._internal.config_parsing.validator as validator_module


def test_build_aggregate_field_index_returns_empty_when_fields_not_dict() -> None:
    validator = validator_module.ConfigValidator()

    alias_index, field_defs = validator._build_aggregate_field_index({"fields": []})  # noqa: SLF001
    assert alias_index == {}
    assert field_defs == []


def test_build_aggregate_field_index_skips_blank_id_and_non_dict_value() -> None:
    validator = validator_module.ConfigValidator()

    alias_index, field_defs = validator._build_aggregate_field_index(  # noqa: SLF001
        {
            "fields": {
                "": {"count": {}},
                "  ": {"count": {}},
                "bad": 1,
                "ok": {"count": {}},
            }
        }
    )
    assert list(alias_index.values()) == ["ok"]
    assert [out_field_id for out_field_id, _data in field_defs] == ["ok"]
