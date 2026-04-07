import pytest

from scalim.dsl.yaml_dsl._internal.config_parsing.error_envelope import ScalimYamlValidationError
from scalim.dsl.yaml_dsl._internal.config_parsing.loader import YamlDemandLoader
from scalim.dsl.yaml_dsl._internal.config_parsing.security import SecureComputeEngine, ScalimSecurityError
from tests.support.yaml_fixtures import make_yaml_config


class TestYamlDemandLoader:
    def test_load_string_basic(self) -> None:
        yaml_content = make_yaml_config(
            name="test_demand",
            description="A test demand",
            main_source="""
source_id: orders
loader: "tests.fixtures.mock_loaders.mock_loader"
fields:
  order_id:
    extract: order_id
    name: Order ID
""",
            sources="{}",
        )
        loader = YamlDemandLoader()
        config = loader.load_string(yaml_content)

        assert config.name == "test_demand"
        assert config.description == "A test demand"
        assert config.main_source is not None
        assert config.main_source.source_id == "orders"
        assert "order_id" in config.source_fields
        assert config.source_fields["order_id"].name == "Order ID"

    def test_load_string_with_derived_fields(self) -> None:
        yaml_content = make_yaml_config(
            name="test_with_derived",
            main_source="""
source_id: orders
loader: "tests.fixtures.mock_loaders.mock_loader"
fields:
  quantity:
    extract: quantity
    name: Quantity

  unit_price:
    extract: unit_price
    name: Unit Price
""",
            sources="{}",
            fields="""
total:
  name: Total
  compute: "quantity * unit_price"
""",
        )
        loader = YamlDemandLoader()
        config = loader.load_string(yaml_content)

        assert "total" in config.derived_fields
        derived = config.derived_fields["total"]
        assert derived.compute == "quantity * unit_price"
        assert derived.depends_on == ("quantity", "unit_price")

    def test_load_string_with_constant_compute_allows_empty_depends_on(self) -> None:
        yaml_content = make_yaml_config(
            name="test_constant_compute",
            main_source="""
source_id: orders
loader: "tests.fixtures.mock_loaders.mock_loader"
fields:
  order_id:
    extract: order_id
""",
            sources="{}",
            fields="""
constant:
  name: Constant
  compute: "1 + 2"
""",
        )
        loader = YamlDemandLoader()
        config = loader.load_string(yaml_content)

        derived = config.derived_fields["constant"]
        assert derived.compute == "1 + 2"
        assert derived.depends_on == ()

    def test_load_string_with_compute_auto_depends_on(self) -> None:
        yaml_content = make_yaml_config(
            name="test_auto_depends_on",
            main_source="""
source_id: orders
loader: "tests.fixtures.mock_loaders.mock_loader"
fields:
  a:
    extract: a
    name: A

  b:
    extract: b
    name: B

  flag:
    extract: flag
    name: Flag

  c:
    extract: c
    name: C
""",
            sources="{}",
            fields="""
result:
  name: Result
  compute: "a + b if flag else c"
""",
        )
        loader = YamlDemandLoader()
        config = loader.load_string(yaml_content)

        derived = config.derived_fields["result"]
        assert set(derived.depends_on) == {"a", "b", "flag", "c"}
        assert len(derived.depends_on) == 4

    def test_load_string_with_compute_explicit_depends_on_rejected(self) -> None:
        yaml_content = make_yaml_config(
            name="test_explicit_depends_on",
            main_source="""
source_id: orders
loader: "tests.fixtures.mock_loaders.mock_loader"
fields:
  a:
    extract: a
    name: A

  b:
    extract: b
    name: B
""",
            sources="{}",
            fields="""
result:
  name: Result
  compute: "a + b"
  depends_on: ["a", "b"]
        """,
        )
        loader = YamlDemandLoader()
        with pytest.raises(ScalimYamlValidationError) as exc_info:
            _ = loader.load_string(yaml_content)
        assert any("does not allow 'depends_on'" in env.message for env in exc_info.value.errors)

    def test_load_string_with_call_by_auto_depends_on(self) -> None:
        yaml_content = make_yaml_config(
            name="test_call_by_auto_depends_on",
            main_source="""
source_id: orders
loader: "tests.fixtures.mock_loaders.mock_loader"
fields:
  a:
    extract: a
  b:
    extract: b
""",
            sources="{}",
            fields="""
result:
  name: Result
  call_by: "tests.fixtures.call_by_fns:add(a, b=b, c=1)"
""",
        )
        loader = YamlDemandLoader()
        config = loader.load_string(yaml_content)

        derived = config.derived_fields["result"]
        assert derived.call_by == "tests.fixtures.call_by_fns:add(a, b=b, c=1)"
        assert derived.depends_on == ("a", "b")

    def test_load_string_with_call_by_explicit_depends_on_rejected(self) -> None:
        yaml_content = make_yaml_config(
            name="test_call_by_explicit_depends_on",
            main_source="""
source_id: orders
loader: "tests.fixtures.mock_loaders.mock_loader"
fields:
  a:
    extract: a
  b:
    extract: b
  extra:
    extract: extra
""",
            sources="{}",
            fields="""
result:
  name: Result
  call_by: "tests.fixtures.call_by_fns:add(a, b=b)"
  depends_on: ["a", "b", "extra"]
        """,
        )
        loader = YamlDemandLoader()
        with pytest.raises(ScalimYamlValidationError) as exc_info:
            _ = loader.load_string(yaml_content)
        assert any("does not allow 'depends_on'" in env.message for env in exc_info.value.errors)

    def test_load_string_with_compute_empty_deps_call_rejected(self) -> None:
        yaml_content = make_yaml_config(
            name="test_compute_empty_deps_call_rejected",
            main_source="""
source_id: orders
loader: "tests.fixtures.mock_loaders.mock_loader"
fields:
  order_id:
    extract: order_id
""",
            sources="{}",
            fields="""
bad:
  name: Bad
  compute: "int('1')"
        """,
        )
        loader = YamlDemandLoader()
        with pytest.raises(ScalimYamlValidationError) as exc_info:
            _ = loader.load_string(yaml_content)
        assert any("compute has no field dependencies" in env.message for env in exc_info.value.errors)

    def test_load_string_with_relations_steps(self) -> None:
        yaml_content = make_yaml_config(
            name="test_with_relations",
            main_source="""
source_id: orders
loader: "tests.fixtures.mock_loaders.mock_loader"
fields:
  order_id:
    extract: order_id
  customer_id:
    extract: customer_id
""",
            sources="""
customers:
  loader: "tests.fixtures.mock_loaders.mock_loader"
  key: customer_id
  params:
    ids: {$keys: {as: set}}
  fields:
    customer_name:
      extract: customer_name
      relation:
        steps:
          - from: orders.customer_id
            to: customers.customer_id
""",
            relations="""
orders_to_customers:
  steps:
    - from: orders.customer_id
      to: customers.customer_id
""",
        )
        loader = YamlDemandLoader()
        config = loader.load_string(yaml_content)

        assert "orders_to_customers" in config.relations
        relation = config.relations["orders_to_customers"]
        assert len(relation.steps) == 1
        assert relation.steps[0].from_ == "orders.customer_id"

    def test_load_string_with_inline_via(self) -> None:
        yaml_content = make_yaml_config(
            name="test_inline_via",
            main_source="""
source_id: orders
loader: "tests.fixtures.mock_loaders.mock_loader"
fields:
  customer_id:
    extract: customer_id
""",
            sources="""
customers:
  loader: "tests.fixtures.mock_loaders.mock_loader"
  key: customer_id
  params:
    ids: {$keys: {as: set}}
  fields:
    customer_name:
      extract: customer_name
      relation:
        steps:
          - from: orders.customer_id
            to: customers.customer_id
""",
        )
        loader = YamlDemandLoader()
        config = loader.load_string(yaml_content)

        field = config.source_fields["customer_name"]
        assert field.relation is not None
        assert len(field.relation.steps) == 1

    def test_load_string_with_value_cast(self) -> None:
        yaml_content = make_yaml_config(
            name="test_value_cast",
            main_source="""
source_id: orders
loader: "tests.fixtures.mock_loaders.mock_loader"
fields:
  amount:
    extract: amount
    value_cast: int
""",
            sources="{}",
        )
        loader = YamlDemandLoader()
        config = loader.load_string(yaml_content)

        assert config.source_fields["amount"].value_cast == "int"


class TestSecureComputeEngine:
    def test_compile_simple_expression(self) -> None:
        engine = SecureComputeEngine()
        calc = engine.compile("a + b", ("a", "b"))

        result = calc(a=10, b=5)
        assert result == 15

    def test_compile_complex_expression(self) -> None:
        engine = SecureComputeEngine()
        calc = engine.compile("(a * b) - c / 2", ("a", "b", "c"))

        result = calc(a=10, b=5, c=20)
        assert result == 40.0

    def test_compile_with_builtin_function(self) -> None:
        engine = SecureComputeEngine()
        calc = engine.compile("max(a, b)", ("a", "b"))

        result = calc(a=10, b=5)
        assert result == 10

    def test_reject_forbidden_name(self) -> None:
        engine = SecureComputeEngine()

        with pytest.raises(ScalimSecurityError) as exc_info:
            engine.compile("__import__('os')", ("x",))

        assert "__import__" in str(exc_info.value)

    def test_reject_unknown_function(self) -> None:
        engine = SecureComputeEngine()

        with pytest.raises(ScalimSecurityError) as exc_info:
            engine.compile("open('file.txt')", ("x",))

        assert "open" in str(exc_info.value)

    def test_reject_unknown_variable(self) -> None:
        engine = SecureComputeEngine()

        with pytest.raises(ScalimSecurityError) as exc_info:
            engine.compile("a + unknown_var", ("a",))

        assert "unknown_var" in str(exc_info.value)

    def test_comparison_expression(self) -> None:
        engine = SecureComputeEngine()
        calc = engine.compile("a > b", ("a", "b"))

        assert calc(a=10, b=5) is True
        assert calc(a=5, b=10) is False

    def test_conditional_expression(self) -> None:
        engine = SecureComputeEngine()
        calc = engine.compile("a if a > b else b", ("a", "b"))

        assert calc(a=10, b=5) == 10
        assert calc(a=5, b=10) == 10
