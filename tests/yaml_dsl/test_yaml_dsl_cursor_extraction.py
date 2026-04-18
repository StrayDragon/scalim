import textwrap

import pytest

import scalim_yaml_dsl_lsp.core as editor_semantics


def _pos(text: str, needle: str, *, offset: int = 0) -> editor_semantics.EditorPosition:
    idx = text.index(needle) + int(offset)
    line = text.count("\n", 0, idx) + 1
    line_start = text.rfind("\n", 0, idx)
    if line_start == -1:
        line_start = 0
    else:
        line_start += 1
    column = idx - line_start + 1
    return editor_semantics.EditorPosition(line=int(line), column=int(column))


def _range_for(text: str, needle: str) -> editor_semantics.EditorRange:
    start = _pos(text, needle, offset=0)
    end = editor_semantics.EditorPosition(line=start.line, column=start.column + len(needle))
    return editor_semantics.EditorRange(start=start, end=end)


@pytest.mark.parametrize(
    ("yaml_value", "expected_reference"),
    [
        ("pkg.mod:fn", "pkg.mod:fn"),
        ("pkg.mod.fn", "pkg.mod.fn"),
        ('"pkg.mod:fn"', "pkg.mod:fn"),
    ],
)
def test_cursor_extraction_loader_supports_quoted_and_unquoted(yaml_value: str, expected_reference: str) -> None:
    yaml_text = textwrap.dedent(
        f"""\
        name: demo
        main_source:
          source_id: orders
          loader: {yaml_value}
        sources: {{}}
        """
    )
    pos = _pos(yaml_text, expected_reference, offset=2)
    result = editor_semantics.extract_yaml_dsl_python_reference_by_cursor(yaml_text, pos)
    assert result.yaml_path == "main_source.loader"
    assert result.reference == expected_reference
    assert result.range == _range_for(yaml_text, expected_reference)
    assert result.warnings == ()


def test_cursor_extraction_call_by_parses_head_and_range() -> None:
    yaml_text = textwrap.dedent(
        """\
        name: demo
        call_by: "pkg.mod:fn(a=1)"
        sources: {}
        """
    )
    pos = _pos(yaml_text, "pkg.mod:fn", offset=2)
    result = editor_semantics.extract_yaml_dsl_python_reference_by_cursor(yaml_text, pos)
    assert result.yaml_path == "call_by"
    assert result.reference == "pkg.mod:fn"
    assert result.range == _range_for(yaml_text, "pkg.mod:fn")

    args_pos = _pos(yaml_text, "a=1", offset=1)
    result2 = editor_semantics.extract_yaml_dsl_python_reference_by_cursor(yaml_text, args_pos)
    assert result2.reference == ""
    assert result2.range is None


def test_cursor_extraction_call_by_head_supports_block_scalar() -> None:
    yaml_text = textwrap.dedent(
        """\
        name: demo
        main_source: {source_id: orders, loader: scalim_misc.demo_big_data_report.loaders:load_orders}
        sources: {}
        fields:
          profit:
            call_by: |
              pkg.mod:fn(
                order_amount=order_amount,
              )
        """
    )
    pos = _pos(yaml_text, "pkg.mod:fn", offset=2)
    result = editor_semantics.extract_yaml_dsl_python_reference_by_cursor(yaml_text, pos)
    assert result.yaml_path == "fields.profit.call_by"
    assert result.reference == "pkg.mod:fn"
    assert result.range == _range_for(yaml_text, "pkg.mod:fn")

    args_pos = _pos(yaml_text, "order_amount=order_amount", offset=2)
    result2 = editor_semantics.extract_yaml_dsl_python_reference_by_cursor(yaml_text, args_pos)
    assert result2.reference == ""
    assert result2.range is None


def test_cursor_extraction_call_by_kwargs_value_supports_block_scalar_multiline_and_comments() -> None:
    yaml_text = textwrap.dedent(
        """\
        name: demo
        main_source: {source_id: orders, loader: scalim_misc.demo_big_data_report.loaders:load_orders}
        sources: {}
        fields:
          profit:
            call_by: |
              pkg.mod:fn(
                order_amount=order_amount, # comment with ) should be ignored
                other=, # empty for completion
              )  # tail
        """
    )
    rhs_start = _pos(yaml_text, "order_amount=order_amount", offset=len("order_amount="))
    rhs_pos = editor_semantics.EditorPosition(line=rhs_start.line, column=rhs_start.column + 2)
    rhs = editor_semantics.extract_yaml_dsl_call_by_kwargs_value_field_reference_by_cursor(yaml_text, rhs_pos)
    assert rhs.kind == "call_by_kwargs_value_field_ref"
    assert rhs.yaml_path == "fields.profit.call_by"
    assert rhs.reference == "order_amount"
    assert rhs.range == editor_semantics.EditorRange(
        start=rhs_start,
        end=editor_semantics.EditorPosition(line=rhs_start.line, column=rhs_start.column + len("order_amount")),
    )

    empty_pos = _pos(yaml_text, "other=", offset=len("other="))
    empty = editor_semantics.extract_yaml_dsl_call_by_kwargs_value_field_reference_by_cursor(yaml_text, empty_pos)
    assert empty.kind == "call_by_kwargs_value_field_ref"
    assert empty.yaml_path == "fields.profit.call_by"
    assert empty.reference == ""
    assert empty.range == editor_semantics.EditorRange(start=empty_pos, end=empty_pos)
    assert empty.value_range == empty.range


def test_cursor_extraction_call_by_kwargs_value_extracts_rhs_field_id_and_ignores_lhs_name() -> None:
    yaml_text = textwrap.dedent(
        """\
        name: demo
        main_source: {source_id: orders, loader: scalim_misc.demo_big_data_report.loaders:load_orders}
        sources: {}
        fields:
          profit:
            call_by: "pkg.mod:fn(order_amount=order_amount)"
        """
    )
    lhs_pos = _pos(yaml_text, "order_amount=order_amount", offset=2)
    lhs = editor_semantics.extract_yaml_dsl_call_by_kwargs_value_field_reference_by_cursor(yaml_text, lhs_pos)
    assert lhs.reference == ""
    assert lhs.range is None

    rhs_start = _pos(yaml_text, "order_amount=order_amount", offset=len("order_amount="))
    rhs_pos = editor_semantics.EditorPosition(line=rhs_start.line, column=rhs_start.column + 2)
    rhs = editor_semantics.extract_yaml_dsl_call_by_kwargs_value_field_reference_by_cursor(yaml_text, rhs_pos)
    assert rhs.kind == "call_by_kwargs_value_field_ref"
    assert rhs.yaml_path == "fields.profit.call_by"
    assert rhs.reference == "order_amount"
    assert rhs.range == editor_semantics.EditorRange(
        start=rhs_start,
        end=editor_semantics.EditorPosition(line=rhs_start.line, column=rhs_start.column + len("order_amount")),
    )
    assert rhs.value == "order_amount"
    assert rhs.value_range == rhs.range


def test_cursor_extraction_call_by_kwargs_value_supports_empty_value_for_completion() -> None:
    yaml_text = textwrap.dedent(
        """\
        name: demo
        main_source: {source_id: orders, loader: scalim_misc.demo_big_data_report.loaders:load_orders}
        sources: {}
        fields:
          profit:
            call_by: "pkg.mod:fn(order_amount=)"
        """
    )
    pos = _pos(yaml_text, "order_amount=", offset=len("order_amount="))
    result = editor_semantics.extract_yaml_dsl_call_by_kwargs_value_field_reference_by_cursor(yaml_text, pos)
    assert result.kind == "call_by_kwargs_value_field_ref"
    assert result.yaml_path == "fields.profit.call_by"
    assert result.reference == ""
    assert result.range == editor_semantics.EditorRange(start=pos, end=pos)
    assert result.value_range == result.range


def test_cursor_extraction_call_by_kwargs_value_supports_builtin_call_by_head() -> None:
    yaml_text = textwrap.dedent(
        """\
        name: demo
        main_source: {source_id: orders, loader: scalim_misc.demo_big_data_report.loaders:load_orders}
        sources: {}
        fields:
          score:
            call_by: "^score_by_rank(rank=rank, base=100, step=3)"
        """
    )
    rhs_start = _pos(yaml_text, "rank=rank", offset=len("rank="))
    rhs_pos = editor_semantics.EditorPosition(line=rhs_start.line, column=rhs_start.column + 1)
    result = editor_semantics.extract_yaml_dsl_call_by_kwargs_value_field_reference_by_cursor(yaml_text, rhs_pos)
    assert result.kind == "call_by_kwargs_value_field_ref"
    assert result.yaml_path == "fields.score.call_by"
    assert result.reference == "rank"
    assert result.range == editor_semantics.EditorRange(
        start=rhs_start,
        end=editor_semantics.EditorPosition(line=rhs_start.line, column=rhs_start.column + len("rank")),
    )


def test_cursor_extraction_call_by_kwargs_value_supports_aggregate_callsite() -> None:
    yaml_text = textwrap.dedent(
        """\
        name: demo
        main_source: {source_id: orders, loader: scalim_misc.demo_big_data_report.loaders:load_orders, fields: {order_amount: {}}}
        sources: {}
        outputs:
          - name: out
            to: {file: out.xlsx}
            aggregate:
              group_by: [order_amount]
              fields:
                sum_amount: {sum: {field: order_amount}}
                score:
                  call_by: "^score_by_rank(rank=sum_amount, base=100, step=3)"
        """
    )
    rhs_start = _pos(yaml_text, "rank=sum_amount", offset=len("rank="))
    rhs_pos = editor_semantics.EditorPosition(line=rhs_start.line, column=rhs_start.column + 2)
    result = editor_semantics.extract_yaml_dsl_call_by_kwargs_value_field_reference_by_cursor(yaml_text, rhs_pos)
    assert result.kind == "call_by_kwargs_value_field_ref"
    assert result.yaml_path == "outputs.0.aggregate.fields.score.call_by"
    assert result.reference == "sum_amount"
    assert result.range == editor_semantics.EditorRange(
        start=rhs_start,
        end=editor_semantics.EditorPosition(line=rhs_start.line, column=rhs_start.column + len("sum_amount")),
    )


def test_cursor_extraction_call_by_kwargs_value_supports_ref_default_callsite() -> None:
    yaml_text = textwrap.dedent(
        """\
        name: demo
        main_source: {source_id: orders, loader: pkg.mod:load}
        sources:
          s1:
            loader: pkg.mod:load
            key: id
            fields:
              f1:
                relation: {steps: [{from: orders.id, to: s1.id}]}
                default:
                  - when: relation_miss
                    call_by: "pkg.mod:fn(group=group_name)"
        """
    )
    rhs_start = _pos(yaml_text, "group=group_name", offset=len("group="))
    rhs_pos = editor_semantics.EditorPosition(line=rhs_start.line, column=rhs_start.column + 2)
    result = editor_semantics.extract_yaml_dsl_call_by_kwargs_value_field_reference_by_cursor(yaml_text, rhs_pos)
    assert result.kind == "call_by_kwargs_value_field_ref"
    assert result.yaml_path == "sources.s1.fields.f1.default.0.call_by"
    assert result.reference == "group_name"


def test_cursor_extraction_retry_should_retry_supports_nested_path() -> None:
    yaml_text = textwrap.dedent(
        """\
        retry:
          should_retry: pkg.mod:pred
        """
    )
    pos = _pos(yaml_text, "pkg.mod:pred", offset=2)
    result = editor_semantics.extract_yaml_dsl_python_reference_by_cursor(yaml_text, pos)
    assert result.yaml_path == "retry.should_retry"
    assert result.reference == "pkg.mod:pred"
    assert result.range == _range_for(yaml_text, "pkg.mod:pred")


def test_cursor_extraction_returns_empty_when_cursor_not_in_value() -> None:
    yaml_text = "loader: pkg.mod:fn\n"
    pos = _pos(yaml_text, "loader", offset=2)
    result = editor_semantics.extract_yaml_dsl_python_reference_by_cursor(yaml_text, pos)
    assert result.reference == ""
    assert result.range is None


def test_cursor_extraction_degrades_on_yaml_parse_error() -> None:
    yaml_text = "name: [\n"
    result = editor_semantics.extract_yaml_dsl_python_reference_by_cursor(
        yaml_text,
        editor_semantics.EditorPosition(line=1, column=1),
    )
    assert result.reference == ""
    assert result.range is None
    assert result.warnings


def test_cursor_extraction_loader_allows_cursor_at_end_of_reference() -> None:
    yaml_text = textwrap.dedent(
        """\
        name: demo
        main_source:
          source_id: orders
          loader: "pkg.mod:fn"
        sources: {}
        """
    )
    reference = "pkg.mod:fn"
    end_pos = _pos(yaml_text, reference, offset=len(reference))
    result = editor_semantics.extract_yaml_dsl_python_reference_by_cursor(yaml_text, end_pos)
    assert result.yaml_path == "main_source.loader"
    assert result.reference == reference


def test_cursor_extraction_outputs_fields_scalar_is_supported() -> None:
    yaml_text = textwrap.dedent(
        """\
        name: demo
        main_source:
          source_id: orders
          loader: tests.fixtures.mock_loaders.mock_loader
        sources: {}
        outputs:
          - name: out
            to: {file: out.xlsx}
            fields:
              - a
        """
    )
    pos = _pos(yaml_text, "- a", offset=2)
    expected_range = editor_semantics.EditorRange(
        start=pos,
        end=editor_semantics.EditorPosition(line=pos.line, column=pos.column + 1),
    )
    result = editor_semantics.extract_yaml_dsl_output_field_reference_by_cursor(yaml_text, pos)
    assert result.kind == "output_field_id"
    assert result.yaml_path == "outputs.0.fields.0"
    assert result.reference == "a"
    assert result.range == expected_range
    assert result.value == "a"
    assert result.value_range == expected_range


def test_cursor_extraction_outputs_fields_nested_list_is_supported() -> None:
    yaml_text = textwrap.dedent(
        """\
        name: demo
        main_source: {source_id: orders, loader: tests.fixtures.mock_loaders.mock_loader}
        sources: {}
        outputs:
          - name: out
            to: {file: out.xlsx}
            fields:
              - [a, b]
        """
    )
    pos = _pos(yaml_text, "[a, b]", offset=4)
    expected_range = editor_semantics.EditorRange(
        start=pos,
        end=editor_semantics.EditorPosition(line=pos.line, column=pos.column + 1),
    )
    result = editor_semantics.extract_yaml_dsl_output_field_reference_by_cursor(yaml_text, pos)
    assert result.kind == "output_field_id"
    assert result.yaml_path == "outputs.0.fields.0.1"
    assert result.reference == "b"
    assert result.range == expected_range


def test_cursor_extraction_outputs_fields_empty_scalar_is_supported_for_completion() -> None:
    yaml_text = textwrap.dedent(
        """\
        name: demo
        main_source: {source_id: orders, loader: tests.fixtures.mock_loaders.mock_loader, fields: {a: {}}}
        sources: {}
        outputs:
          - name: out
            to: {file: out.xlsx}
            fields:
              - 
        """
    )
    needle = "      - "
    pos = _pos(yaml_text, needle, offset=len(needle))
    result = editor_semantics.extract_yaml_dsl_output_field_reference_by_cursor(yaml_text, pos)
    assert result.kind == "output_field_id"
    assert result.yaml_path == "outputs.0.fields.0"
    assert result.reference == ""
    assert result.range is not None
    assert result.value_range is not None


def test_cursor_extraction_outputs_aggregate_group_by_scalar_is_supported() -> None:
    yaml_text = textwrap.dedent(
        """\
        name: demo
        main_source: {source_id: orders, loader: tests.fixtures.mock_loaders.mock_loader, fields: {a: {}, b: {}}}
        sources: {}
        outputs:
          - name: out
            to: {file: out.xlsx}
            aggregate:
              group_by: [a]
              fields:
                cnt: {count: {}}
        """
    )
    pos = _pos(yaml_text, "group_by: [a]", offset=len("group_by: ["))
    expected_range = editor_semantics.EditorRange(
        start=pos,
        end=editor_semantics.EditorPosition(line=pos.line, column=pos.column + 1),
    )
    result = editor_semantics.extract_yaml_dsl_aggregate_field_reference_by_cursor(yaml_text, pos)
    assert result.kind == "aggregate_field_ref"
    assert result.yaml_path == "outputs.0.aggregate.group_by.0"
    assert result.reference == "a"
    assert result.range == expected_range
    assert result.value == "a"
    assert result.value_range == expected_range


def test_cursor_extraction_outputs_aggregate_group_by_composite_list_is_supported() -> None:
    yaml_text = textwrap.dedent(
        """\
        name: demo
        main_source: {source_id: orders, loader: tests.fixtures.mock_loaders.mock_loader, fields: {a: {}, b: {}, c: {}}}
        sources: {}
        outputs:
          - name: out
            to: {file: out.xlsx}
            aggregate:
              group_by: [[a, b], c]
              fields:
                cnt: {count: {}}
        """
    )
    pos = _pos(yaml_text, "[a, b]", offset=4)
    expected_range = editor_semantics.EditorRange(
        start=pos,
        end=editor_semantics.EditorPosition(line=pos.line, column=pos.column + 1),
    )
    result = editor_semantics.extract_yaml_dsl_aggregate_field_reference_by_cursor(yaml_text, pos)
    assert result.kind == "aggregate_field_ref"
    assert result.yaml_path == "outputs.0.aggregate.group_by.0.1"
    assert result.reference == "b"
    assert result.range == expected_range


def test_cursor_extraction_outputs_aggregate_group_by_empty_scalar_is_supported_for_completion() -> None:
    yaml_text = textwrap.dedent(
        """\
        name: demo
        main_source: {source_id: orders, loader: tests.fixtures.mock_loaders.mock_loader, fields: {a: {}, b: {}}}
        sources: {}
        outputs:
          - name: out
            to: {file: out.xlsx}
            aggregate:
              group_by:
                - 
              fields:
                cnt: {count: {}}
        """
    )
    needle = "        - "
    pos = _pos(yaml_text, needle, offset=len(needle))
    result = editor_semantics.extract_yaml_dsl_aggregate_field_reference_by_cursor(yaml_text, pos)
    assert result.kind == "aggregate_field_ref"
    assert result.yaml_path == "outputs.0.aggregate.group_by.0"
    assert result.reference == ""
    assert result.range is not None
    assert result.value_range is not None


def test_cursor_extraction_outputs_aggregate_metric_field_ref_is_supported() -> None:
    yaml_text = textwrap.dedent(
        """\
        name: demo
        main_source: {source_id: orders, loader: tests.fixtures.mock_loaders.mock_loader, fields: {order_amount: {}}}
        sources: {}
        outputs:
          - name: out
            to: {file: out.xlsx}
            aggregate:
              group_by: [order_amount]
              fields:
                sum_amount: {sum: {field: order_amount}}
        """
    )
    pos = _pos(yaml_text, "sum_amount: {sum: {field: order_amount}}", offset=len("sum_amount: {sum: {field: "))
    expected_range = editor_semantics.EditorRange(
        start=pos,
        end=editor_semantics.EditorPosition(line=pos.line, column=pos.column + len("order_amount")),
    )
    result = editor_semantics.extract_yaml_dsl_aggregate_field_reference_by_cursor(yaml_text, pos)
    assert result.kind == "aggregate_field_ref"
    assert result.yaml_path == "outputs.0.aggregate.fields.sum_amount.sum.field"
    assert result.reference == "order_amount"
    assert result.range == expected_range


def test_cursor_extraction_outputs_aggregate_metric_fields_list_ref_is_supported() -> None:
    yaml_text = textwrap.dedent(
        """\
        name: demo
        main_source: {source_id: orders, loader: tests.fixtures.mock_loaders.mock_loader, fields: {customer_id: {}, product_id: {}}}
        sources: {}
        outputs:
          - name: out
            to: {file: out.xlsx}
            aggregate:
              group_by: [customer_id]
              fields:
                customer_product_cnt: {count_distinct: {fields: [customer_id, product_id]}}
        """
    )
    pos = _pos(yaml_text, "fields: [customer_id, product_id]", offset=len("fields: [customer_id, "))
    expected_range = editor_semantics.EditorRange(
        start=pos,
        end=editor_semantics.EditorPosition(line=pos.line, column=pos.column + len("product_id")),
    )
    result = editor_semantics.extract_yaml_dsl_aggregate_field_reference_by_cursor(yaml_text, pos)
    assert result.kind == "aggregate_field_ref"
    assert result.yaml_path == "outputs.0.aggregate.fields.customer_product_cnt.count_distinct.fields.1"
    assert result.reference == "product_id"
    assert result.range == expected_range


def test_cursor_extraction_outputs_aggregate_rank_refs_are_supported_and_do_not_mis_hit_other_by_keys() -> None:
    yaml_text = textwrap.dedent(
        """\
        name: demo
        main_source: {source_id: orders, loader: tests.fixtures.mock_loaders.mock_loader, fields: {region_id: {}, product_id: {}, order_amount: {}}}
        sources: {}
        by: should_not_match
        outputs:
          - name: out
            to: {file: out.xlsx}
            aggregate:
              group_by: [region_id]
              fields:
                sum_amount: {sum: {field: order_amount}}
                rank:
                  dense_rank:
                    by: sum_amount
                    partition_by: [region_id]
                    order: desc
                    order_by: [sum_amount, product_id]
                score:
                  score_by_rank:
                    rank_field: rank
        """
    )
    by_pos = _pos(yaml_text, "by: should_not_match", offset=len("by: "))
    by_result = editor_semantics.extract_yaml_dsl_aggregate_field_reference_by_cursor(yaml_text, by_pos)
    assert by_result.kind == ""
    assert by_result.range is None

    rank_by_pos = _pos(yaml_text, "by: sum_amount", offset=len("by: "))
    rank_by_result = editor_semantics.extract_yaml_dsl_aggregate_field_reference_by_cursor(yaml_text, rank_by_pos)
    assert rank_by_result.kind == "aggregate_field_ref"
    assert rank_by_result.yaml_path == "outputs.0.aggregate.fields.rank.dense_rank.by"
    assert rank_by_result.reference == "sum_amount"

    partition_pos = _pos(yaml_text, "partition_by: [region_id]", offset=len("partition_by: ["))
    partition_result = editor_semantics.extract_yaml_dsl_aggregate_field_reference_by_cursor(yaml_text, partition_pos)
    assert partition_result.kind == "aggregate_field_ref"
    assert partition_result.yaml_path == "outputs.0.aggregate.fields.rank.dense_rank.partition_by.0"
    assert partition_result.reference == "region_id"

    order_by_pos = _pos(yaml_text, "order_by: [sum_amount, product_id]", offset=len("order_by: [sum_amount, "))
    order_by_result = editor_semantics.extract_yaml_dsl_aggregate_field_reference_by_cursor(yaml_text, order_by_pos)
    assert order_by_result.kind == "aggregate_field_ref"
    assert order_by_result.yaml_path == "outputs.0.aggregate.fields.rank.dense_rank.order_by.1"
    assert order_by_result.reference == "product_id"

    score_pos = _pos(yaml_text, "rank_field: rank", offset=len("rank_field: "))
    score_result = editor_semantics.extract_yaml_dsl_aggregate_field_reference_by_cursor(yaml_text, score_pos)
    assert score_result.kind == "aggregate_field_ref"
    assert score_result.yaml_path == "outputs.0.aggregate.fields.score.score_by_rank.rank_field"
    assert score_result.reference == "rank"


def test_cursor_extraction_yaml_import_ref_empty_scalar_is_supported_for_completion() -> None:
    yaml_text = textwrap.dedent(
        """\
        name: demo
        imports:
          fragments: ./frag.yaml
        main_source:
          source_id: orders
          loader: tests.fixtures.mock_loaders.mock_loader
          params:
            $import:
          order_by: [order_id]
        sources: {}
        outputs: []
        """
    )
    pos = _pos(yaml_text, "$import:", offset=len("$import:"))
    result = editor_semantics.extract_yaml_dsl_import_reference_by_cursor(yaml_text, pos)
    assert result.kind == "$import"
    assert result.reference == ""
    assert result.range is not None
    assert result.value_range is not None


def test_cursor_extraction_yaml_alias_token_is_supported() -> None:
    yaml_text = textwrap.dedent(
        """\
        detail_fields: &detail_fields [a, b]
        name: demo
        main_source: {source_id: orders, loader: tests.fixtures.mock_loaders.mock_loader}
        sources: {}
        outputs:
          - name: out
            to: {file: out.xlsx}
            fields:
              - *detail_fields
        """
    )
    pos = _pos(yaml_text, "*detail_fields", offset=2)
    result = editor_semantics.extract_yaml_dsl_yaml_alias_reference_by_cursor(yaml_text, pos)
    assert result.kind == "yaml_alias"
    assert result.reference == "detail_fields"
    assert result.range == _range_for(yaml_text, "*detail_fields")
    assert result.value == "*detail_fields"
    assert result.value_range == _range_for(yaml_text, "*detail_fields")


def test_cursor_extraction_expression_token_in_fields_compute_is_supported() -> None:
    yaml_text = textwrap.dedent(
        """\
        name: demo
        main_source: {source_id: orders, loader: tests.fixtures.mock_loaders.mock_loader, fields: {a: {}}}
        sources: {}
        fields:
          sum:
            compute: "a + 1"
        outputs: []
        """
    )
    pos = _pos(yaml_text, 'compute: "a + 1"', offset=len('compute: "') + 0)
    expected_range = editor_semantics.EditorRange(
        start=pos,
        end=editor_semantics.EditorPosition(line=pos.line, column=pos.column + 1),
    )
    result = editor_semantics.extract_yaml_dsl_expression_token_by_cursor(yaml_text, pos)
    assert result.kind == "expression_fields_compute"
    assert result.yaml_path == "fields.sum.compute"
    assert result.reference == "a"
    assert result.range == expected_range
    assert result.value == "a"
    assert result.value_range == expected_range


def test_cursor_extraction_expression_allows_empty_token_inside_expression_scalar() -> None:
    yaml_text = textwrap.dedent(
        """\
        name: demo
        main_source: {source_id: orders, loader: tests.fixtures.mock_loaders.mock_loader, fields: {a: {}}}
        sources: {}
        fields:
          sum:
            compute: "a + 1"
        outputs: []
        """
    )
    pos = _pos(yaml_text, 'compute: "a + 1"', offset=len('compute: "a ') + 0)
    result = editor_semantics.extract_yaml_dsl_expression_token_by_cursor(yaml_text, pos)
    assert result.kind == "expression_fields_compute"
    assert result.yaml_path == "fields.sum.compute"
    assert result.reference == ""
    assert result.range is not None
    assert result.value_range is not None


def test_cursor_extraction_expression_token_in_outputs_where_is_supported() -> None:
    yaml_text = textwrap.dedent(
        """\
        name: demo
        main_source: {source_id: orders, loader: tests.fixtures.mock_loaders.mock_loader, fields: {a: {}, b: {}}}
        sources: {}
        outputs:
          - name: out
            to: {file: out.xlsx}
            where: "a and b"
        """
    )
    pos = _pos(yaml_text, 'where: "a and b"', offset=len('where: "a and ') + 0)
    expected_range = editor_semantics.EditorRange(
        start=pos,
        end=editor_semantics.EditorPosition(line=pos.line, column=pos.column + 1),
    )
    result = editor_semantics.extract_yaml_dsl_expression_token_by_cursor(yaml_text, pos)
    assert result.kind == "expression_outputs_where"
    assert result.yaml_path == "outputs.0.where"
    assert result.reference == "b"
    assert result.range == expected_range


def test_cursor_extraction_expression_token_in_outputs_aggregate_compute_is_supported() -> None:
    yaml_text = textwrap.dedent(
        """\
        name: demo
        main_source: {source_id: orders, loader: tests.fixtures.mock_loaders.mock_loader, fields: {a: {}}}
        sources: {}
        outputs:
          - name: out
            to: {file: out.xlsx}
            aggregate:
              group_by: [a]
              fields:
                cnt:
                  compute: "a + cnt"
        """
    )
    pos = _pos(yaml_text, 'compute: "a + cnt"', offset=len('compute: "a + ') + 0)
    expected_range = editor_semantics.EditorRange(
        start=pos,
        end=editor_semantics.EditorPosition(line=pos.line, column=pos.column + len("cnt")),
    )
    result = editor_semantics.extract_yaml_dsl_expression_token_by_cursor(yaml_text, pos)
    assert result.kind == "expression_outputs_aggregate_compute"
    assert result.yaml_path == "outputs.0.aggregate.fields.cnt.compute"
    assert result.reference == "cnt"
    assert result.range == expected_range
