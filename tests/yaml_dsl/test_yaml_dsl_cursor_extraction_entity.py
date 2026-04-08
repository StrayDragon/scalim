import textwrap

import pytest

import scalim_yaml_dsl_lsp.core as editor_semantics


def _pos_at(text: str, idx: int) -> editor_semantics.EditorPosition:
    line = text.count("\n", 0, idx) + 1
    line_start = text.rfind("\n", 0, idx)
    if line_start == -1:
        line_start = 0
    else:
        line_start += 1
    column = idx - line_start + 1
    return editor_semantics.EditorPosition(line=int(line), column=int(column))


def _range_at(text: str, idx: int, length: int) -> editor_semantics.EditorRange:
    start = _pos_at(text, idx)
    end = editor_semantics.EditorPosition(line=start.line, column=start.column + int(length))
    return editor_semantics.EditorRange(start=start, end=end)


@pytest.mark.parametrize(
    "yaml_value",
    [
        "orders.customer_id",
        '"orders.customer_id"',
        "'orders.customer_id'",
    ],
)
def test_cursor_extraction_entity_relation_step_supports_subtoken_ranges(yaml_value: str) -> None:
    yaml_text = textwrap.dedent(
        f"""\
        name: demo
        main_source:
          source_id: orders
          loader: tests.fixtures.mock_loaders.mock_loader
          fields:
            customer_id: {{name: Customer}}
        sources:
          customers:
            loader: tests.fixtures.mock_loaders.mock_loader
            key: customer_id
            fields:
              customer_id: {{name: Customer}}
        relations:
          orders_to_customers:
            steps:
              - from: {yaml_value}
                to: customers.customer_id
        outputs: []
        """
    )

    full_idx = yaml_text.index("orders.customer_id")
    orders_idx = full_idx
    field_idx = full_idx + len("orders.")

    # cursor in source_id segment
    pos_orders = _pos_at(yaml_text, orders_idx + 2)
    r_orders = editor_semantics.extract_yaml_dsl_entity_reference_by_cursor(yaml_text, pos_orders)
    assert r_orders.kind == "relation_step_source_id"
    assert r_orders.reference == "orders"
    assert r_orders.value == "orders.customer_id"
    assert r_orders.range == _range_at(yaml_text, orders_idx, len("orders"))
    assert r_orders.value_range == _range_at(yaml_text, full_idx, len("orders.customer_id"))

    # cursor in field_id segment
    pos_field = _pos_at(yaml_text, field_idx + 2)
    r_field = editor_semantics.extract_yaml_dsl_entity_reference_by_cursor(yaml_text, pos_field)
    assert r_field.kind == "relation_step_field_id"
    assert r_field.reference == "customer_id"
    assert r_field.value == "orders.customer_id"
    assert r_field.range == _range_at(yaml_text, field_idx, len("customer_id"))
    assert r_field.value_range == _range_at(yaml_text, full_idx, len("orders.customer_id"))


def test_cursor_extraction_entity_workflow_depends_on_list_item_is_run_id() -> None:
    yaml_text = textwrap.dedent(
        """\
        workflow:
          runs:
            - id: extract
              demand: x.yaml
            - id: transform
              depends_on: [extract]
              demand: y.yaml
        """
    )

    idx = yaml_text.index("[extract]") + 1  # inside extract
    pos = _pos_at(yaml_text, idx + 2)
    result = editor_semantics.extract_yaml_dsl_entity_reference_by_cursor(yaml_text, pos)
    assert result.kind == "workflow_run_id"
    assert result.reference == "extract"
    assert result.range == _range_at(yaml_text, idx, len("extract"))


def test_cursor_extraction_entity_outputs_from_is_output_name() -> None:
    yaml_text = textwrap.dedent(
        """\
        name: demo
        main_source: {source_id: orders, loader: tests.fixtures.mock_loaders.mock_loader}
        sources: {}
        outputs:
          - name: base
            to: {file: out.xlsx}
            fields: []
          - name: derived
            from: base
            to: {file: out2.xlsx}
            fields: []
        """
    )

    idx = yaml_text.index("from: base") + len("from: ")
    pos = _pos_at(yaml_text, idx + 2)
    result = editor_semantics.extract_yaml_dsl_entity_reference_by_cursor(yaml_text, pos)
    assert result.kind == "output_name"
    assert result.reference == "base"


def test_cursor_extraction_entity_relation_id_is_supported_under_fields_relation() -> None:
    yaml_text = textwrap.dedent(
        """\
        name: demo
        main_source: {source_id: orders, loader: tests.fixtures.mock_loaders.mock_loader, fields: {customer_id: {}}}
        sources:
          customers:
            loader: tests.fixtures.mock_loaders.mock_loader
            key: customer_id
            fields:
              customer_name:
                relation: orders_to_customers
        relations:
          orders_to_customers: {steps: [{from: orders.customer_id, to: customers.customer_id}]}
        outputs: []
        """
    )

    idx = yaml_text.index("orders_to_customers")
    pos = _pos_at(yaml_text, idx + 3)
    result = editor_semantics.extract_yaml_dsl_entity_reference_by_cursor(yaml_text, pos)
    assert result.kind == "relation_id"
    assert result.reference == "orders_to_customers"
