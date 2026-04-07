from scalim.dsl.yaml_dsl.runtime.conversion import ConfigToIRConverter
from scalim.dsl.yaml_dsl.runtime.references import PythonReferenceResolver
from scalim.dsl.yaml_dsl.schema_dsl.models import (
    DemandConfig,
    MainSourceConfig,
    RelationConfig,
    RelationStepConfig,
    SourceConfig,
    SourceFieldConfig,
)


def _make_main_source() -> MainSourceConfig:
    return MainSourceConfig(source_id="orders", loader="tests.fixtures.mock_loaders.mock_loader")


def _make_config() -> DemandConfig:
    sources = {
        "customers": SourceConfig(
            source_id="customers",
            loader="tests.fixtures.mock_loaders.mock_loader",
            key="customer_id",
        ),
    }
    relations = {
        "r1": RelationConfig(
            relation_id="r1",
            steps=(RelationStepConfig(from_="orders.customer_id", to="customers.customer_id"),),
        ),
    }
    source_fields = {
        "customer_name": SourceFieldConfig(
            field_id="customer_name",
            source="customers",
            extract="name",
            name="Customer",
            relation=None,
            value_cast=None,
        ),
    }
    return DemandConfig(
        name="demo",
        main_source=_make_main_source(),
        sources=sources,
        source_fields=source_fields,
        derived_fields={},
        relations=relations,
    )


def test_converter_relation_adjacency_built_and_reused() -> None:
    converter = ConfigToIRConverter(resolver=PythonReferenceResolver(allowed_modules=frozenset(["tests.fixtures"])))

    converter.convert(_make_config())

    assert converter._relation_adjacency

    path = converter._infer_unique_path("orders", "customers")
    assert path

    original_adjacency = converter._relation_adjacency
    _ = converter._infer_unique_path("orders", "customers")
    assert converter._relation_adjacency is original_adjacency

    converter._relation_adjacency = {}
    _ = converter._infer_unique_path("orders", "customers")
    assert converter._relation_adjacency is not original_adjacency
    assert converter._relation_adjacency
