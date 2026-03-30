from scalim.dsl.by_yaml.runtime.conversion import ConfigToIRConverter
from scalim.dsl.by_yaml.runtime.references import SecurePythonReferenceResolver
from scalim.dsl.by_yaml.schema_dsl.models import DemandConfig


def test_conversion_sources_resolve_required_field_ids_is_noop() -> None:
    resolver = SecurePythonReferenceResolver(allowed_modules=frozenset(["tests.fixtures"]))
    converter = ConfigToIRConverter(resolver=resolver)

    assert converter._resolve_required_field_ids(DemandConfig()) is None  # noqa: SLF001
