import pytest

from scalim.dsl.by_yaml.config_parsing.errors import ConfigValidationError
from scalim.dsl.by_yaml.config_parsing.loader import YamlDemandLoader


@pytest.mark.parametrize(
    "yaml_content,error_message",
    [
        (
            """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    bad: 1
    good:
      extract: order_id
sources: {}
""",
            "Field 'bad' must be a dictionary",
        ),
        (
            """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
output:
  fields: order_id
""",
            "output.fields must be a list",
        ),
        (
            """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
output:
  fields:
    - 1
""",
            "output.fields[0] must be string sugar (field_id or source.field_id), explicit field object (field_id or field), or alias",
        ),
        (
            """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    name:
      extract: name
sources:
  customers:
    loader: tests.conftest.mock_loader
    key: id
    params:
      ids: {$keys: {as: set}}
    fields:
      name:
        extract: name
relations:
  orders_to_customers:
    steps:
      - from: orders.name
        to: customers.name
output:
  fields:
    - field_id: name
""",
            "Output field 'name' is ambiguous; use 'source.field_id' sugar or add source to explicit field_id object",
        ),
        (
            """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
output:
  fields:
    - field_id: missing
""",
            "Output field 'missing' not found",
        ),
    ],
    ids=[
        "bad-main-field",
        "output-fields-not-list",
        "output-item-type",
        "output-ambiguous-id",
        "output-missing-field",
    ],
)
def test_loader_rejects_output_field_configs(yaml_content: str, error_message: str) -> None:
    loader = YamlDemandLoader()

    with pytest.raises(ConfigValidationError) as exc:
        loader.load_string(yaml_content)

    assert any(error_message in msg for msg in exc.value.errors)


def test_loader_rejects_output_overrides_conflict() -> None:
    loader = YamlDemandLoader()

    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
output:
  fields:
    - field_id: order_id
      name: A
    - field_id: order_id
      name: B
"""

    with pytest.raises(ValueError, match="conflicting overrides"):
        loader.load_string(yaml_content)


def test_loader_parses_output_field_explicit() -> None:
    loader = YamlDemandLoader()

    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
output:
  fields:
    - field_id: order_id
      name: Order ID
"""

    config = loader.load_string(yaml_content)

    assert config.output is not None
    assert config.output.fields == ["order_id"]


def test_loader_parses_output_field_string_sugar() -> None:
    loader = YamlDemandLoader()

    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
output:
  fields:
    - order_id
"""

    config = loader.load_string(yaml_content)

    assert config.output is not None
    assert config.output.fields == ["order_id"]


def test_loader_parses_output_field_source_field_id_sugar() -> None:
    loader = YamlDemandLoader()

    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    dup:
      extract: id
sources:
  other:
    loader: tests.conftest.mock_loader
    key: id
    params:
      ids: {$keys: {as: set}}
    fields:
      dup:
        extract: id2
relations:
  orders_to_other:
    steps:
      - from: orders.dup
        to: other.id
output:
  fields:
    - other.dup
"""

    config = loader.load_string(yaml_content)

    assert config.output is not None
    assert config.output.fields == ["dup"]


def test_loader_output_field_explicit_source_resolves() -> None:
    loader = YamlDemandLoader()

    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    dup:
      extract: id
sources:
  other:
    loader: tests.conftest.mock_loader
    key: id
    params:
      ids: {$keys: {as: set}}
    fields:
      dup:
        extract: id2
relations:
  orders_to_other:
    steps:
      - from: orders.dup
        to: other.id
output:
  fields:
    - field_id: dup
      source: other
"""
    config = loader.load_string(yaml_content)

    assert config.output is not None
    assert config.output.fields == ["dup"]


def test_loader_output_field_explicit_source_no_match() -> None:
    loader = YamlDemandLoader()

    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    dup:
      extract: id
sources:
  other:
    loader: tests.conftest.mock_loader
    key: id
    params:
      ids: {$keys: {as: set}}
    fields:
      dup:
        extract: id
relations:
  orders_to_other:
    steps:
      - from: orders.id
        to: other.id
output:
  fields:
    - field_id: dup
      source: missing
"""

    with pytest.raises(ConfigValidationError) as exc:
        loader.load_string(yaml_content)

    assert any("Output field 'dup' has no match for source 'missing'" in msg for msg in exc.value.errors)


def test_loader_rejects_output_field_without_selector_or_alias() -> None:
    loader = YamlDemandLoader()

    missing_field_id = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
output:
  fields:
    - name: Only
"""
    with pytest.raises(ConfigValidationError) as exc:
        loader.load_string(missing_field_id)

    assert any(
        "output.fields[0] must be string sugar (field_id or source.field_id), explicit field object (field_id or field), or alias" in msg
        for msg in exc.value.errors
    )

    null_field_id = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
output:
  fields:
    - field_id:
"""
    with pytest.raises(ConfigValidationError) as exc:
        loader.load_string(null_field_id)

    assert any("output.fields[0] missing field_id; use explicit field_id object" in msg for msg in exc.value.errors)


def test_loader_requires_output_fields_for_duplicate_field_ids() -> None:
    loader = YamlDemandLoader()

    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    dup:
      extract: id
sources:
  other:
    loader: tests.conftest.mock_loader
    key: id
    params:
      ids: {$keys: {as: set}}
    fields:
      dup:
        extract: id2
relations:
  orders_to_other:
    steps:
      - from: orders.dup
        to: other.id
"""

    with pytest.raises(ValueError, match="output.fields is required to disambiguate"):
        loader.load_string(yaml_content)


def test_loader_parses_output_field_by_data_key() -> None:
    loader = YamlDemandLoader()

    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_name:
      extract: order_real_name
      name: 源字段名
sources: {}
output:
  fields:
    - field: order_real_name
      name: 输出字段名
"""

    config = loader.load_string(yaml_content)

    assert config.output is not None
    assert config.output.fields == ["order_name"]
    assert config.main_source.fields["order_name"].name == "输出字段名"


def test_loader_output_field_data_key_requires_source_when_ambiguous() -> None:
    loader = YamlDemandLoader()

    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: id
sources:
  customers:
    loader: tests.conftest.mock_loader
    key: id
    params:
      ids: {$keys: {as: set}}
    fields:
      customer_id:
        extract: id
        relation:
          steps:
            - from: orders.order_id
              to: customers.id
output:
  fields:
    - field: id
"""

    with pytest.raises(ConfigValidationError) as exc:
        loader.load_string(yaml_content)

    assert any("Output field data_key 'id' is ambiguous; add source or use field_id" in msg for msg in exc.value.errors)


def test_loader_output_field_data_key_with_source_resolves() -> None:
    loader = YamlDemandLoader()

    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: id
sources:
  customers:
    loader: tests.conftest.mock_loader
    key: id
    params:
      ids: {$keys: {as: set}}
    fields:
      customer_id:
        extract: id
        relation:
          steps:
            - from: orders.order_id
              to: customers.id
output:
  fields:
    - field: id
      source: customers
"""

    config = loader.load_string(yaml_content)

    assert config.output is not None
    assert config.output.fields == ["customer_id"]


def test_loader_output_field_data_key_ambiguous_in_same_source() -> None:
    loader = YamlDemandLoader()

    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    id_alias_a:
      extract: id
    id_alias_b:
      extract: id
sources: {}
output:
  fields:
    - field: id
      source: orders
"""

    with pytest.raises(ConfigValidationError) as exc:
        loader.load_string(yaml_content)

    assert any("Output field data_key 'id' is ambiguous in source 'orders'; use field_id" in msg for msg in exc.value.errors)


def test_loader_output_field_merge_with_data_key_selector() -> None:
    loader = YamlDemandLoader()

    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_name: &order_name
      extract: order_real_name
      name: 源字段名
sources: {}
output:
  fields:
    - <<: *order_name
      field: order_real_name
      name: 输出覆写名
"""

    config = loader.load_string(yaml_content)

    assert config.output is not None
    assert config.output.fields == ["order_name"]
    assert config.main_source.fields["order_name"].name == "输出覆写名"


def test_loader_rejects_output_field_merge_without_selector() -> None:
    loader = YamlDemandLoader()

    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id: &order_id
      name: 订单ID
sources: {}
output:
  fields:
    - <<: *order_id
      name: 订单ID(输出覆写)
"""

    with pytest.raises(ConfigValidationError) as exc:
        loader.load_string(yaml_content)

    assert any(
        "output.fields[0] must be string sugar (field_id or source.field_id), explicit field object (field_id or field), or alias" in msg
        for msg in exc.value.errors
    )


def test_loader_rejects_duplicate_output_definitions() -> None:
    loader = YamlDemandLoader()

    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    dup:
      extract: id
sources:
  other:
    loader: tests.conftest.mock_loader
    key: id
    params:
      ids: {$keys: {as: set}}
    fields:
      dup:
        extract: id2
relations:
  orders_to_other:
    steps:
      - from: orders.id
        to: other.id
output:
  fields:
    - field_id: dup
      source: orders
    - field_id: dup
      source: other
"""

    with pytest.raises(ConfigValidationError) as exc:
        loader.load_string(yaml_content)

    assert any("Output field 'dup' maps to multiple definitions" in msg for msg in exc.value.errors)


def test_loader_rejects_unknown_derived_dependency() -> None:
    loader = YamlDemandLoader()

    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
fields:
  calc:
    compute: order_id + missing
output:
  fields:
    - field_id: calc
"""

    with pytest.raises(ConfigValidationError) as exc:
        loader.load_string(yaml_content)

    assert any("Derived field 'calc' depends on unknown field" in msg for msg in exc.value.errors)


def test_loader_rejects_ambiguous_derived_dependency() -> None:
    loader = YamlDemandLoader()

    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    dup:
      extract: id
sources:
  other:
    loader: tests.conftest.mock_loader
    key: id
    params:
      ids: {$keys: {as: set}}
    fields:
      dup:
        extract: id2
relations:
  orders_to_other:
    steps:
      - from: orders.id
        to: other.id
fields:
  calc:
    compute: dup
output:
  fields:
    - field_id: calc
"""

    with pytest.raises(ConfigValidationError) as exc:
        loader.load_string(yaml_content)

    assert any("Derived field 'calc' depends on ambiguous field 'dup'" in msg for msg in exc.value.errors)


def test_loader_resolves_derived_dependency_chain() -> None:
    loader = YamlDemandLoader()

    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    amount:
      extract: amount
sources: {}
fields:
  net:
    compute: amount
  total:
    compute: net
output:
  fields:
    - field_id: total
"""
    config = loader.load_string(yaml_content)

    assert "total" in config.derived_fields
    assert "net" in config.derived_fields


def test_loader_resolves_empty_compute_depends_on() -> None:
    loader = YamlDemandLoader()

    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    amount:
      extract: amount
sources: {}
fields:
  calc:
    compute: ""
output:
  fields:
    - field_id: calc
"""
    with pytest.raises(ConfigValidationError) as exc:
        loader.load_string(yaml_content)

    assert any("Derived field 'calc' compute must not be empty" in msg for msg in exc.value.errors)


def test_loader_rejects_relation_ref_string() -> None:
    loader = YamlDemandLoader()

    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    customer_name:
      extract: name
      relation: r1
sources: {}
"""

    with pytest.raises(ConfigValidationError) as exc:
        loader.load_string(yaml_content)

    assert any("unknown relation id" in msg for msg in exc.value.errors)
    assert any("missing 'relations.r1'" in msg for msg in exc.value.errors)


def test_loader_parse_steps_non_list_and_skip_bad_items() -> None:
    loader = YamlDemandLoader()

    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
sources:
  customers:
    loader: tests.conftest.mock_loader
    key: customer_id
    params:
      ids: {$keys: {as: set}}
relations:
  empty_steps:
    steps: bad
  good_steps:
    steps:
      - bad
      - from: orders.customer_id
        to: customers.customer_id
"""
    with pytest.raises(ConfigValidationError) as exc:
        loader.load_string(yaml_content)

    assert any("steps must be a list" in msg or "steps[0] must be a dictionary" in msg for msg in exc.value.errors)
