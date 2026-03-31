from scalim.dsl.by_yaml._internal.config_parsing.loader import YamlDemandLoader
from scalim.dsl.by_yaml.schema_dsl.models import LOADER_RETRY_KEYS


def test_parse_loader_retry_treats_bool_as_none_for_int_fields() -> None:
    loader = YamlDemandLoader()
    parsed = loader._parse_loader_retry({LOADER_RETRY_KEYS["max_attempts"]: True})  # noqa: SLF001

    assert parsed is not None
    assert parsed.max_attempts is None


def test_parse_loader_retry_treats_invalid_numbers_as_none() -> None:
    loader = YamlDemandLoader()
    parsed = loader._parse_loader_retry(  # noqa: SLF001
        {
            LOADER_RETRY_KEYS["max_attempts"]: "nope",
            LOADER_RETRY_KEYS["max_elapsed_seconds"]: "nope",
            LOADER_RETRY_KEYS["base_delay_seconds"]: object(),
            LOADER_RETRY_KEYS["max_delay_seconds"]: False,
        }
    )

    assert parsed is not None
    assert parsed.max_attempts is None
    assert parsed.max_elapsed_seconds is None
    assert parsed.base_delay_seconds is None
    assert parsed.max_delay_seconds is None
