from typing import Any, Dict, List

from scalim.dsl.yaml_dsl._internal.config_parsing.loader import YamlDemandLoader
from scalim.dsl.yaml_dsl.schema_dsl.builder import build_demand_schema


def _load_ok(yaml_text: str) -> None:
    _ = YamlDemandLoader().load_string(yaml_text)


def _enum(schema: Dict[str, Any], *path: str) -> List[str]:
    current: Any = schema
    for key in path:
        assert isinstance(current, dict)
        current = current[key]
    assert isinstance(current, dict)
    values = current.get("enum")
    assert isinstance(values, list)
    return [str(x) for x in values]


def test_schema_enums_match_runtime_validation_for_file_resources() -> None:
    schema = build_demand_schema()
    file_kinds = _enum(schema, "definitions", "file", "properties", "kind")
    header_by_values = _enum(schema, "definitions", "output_write", "properties", "header_fields_output_by")

    for kind in file_kinds:
        _load_ok(
            "\n".join(
                [
                    "name: demo",
                    "main_source:",
                    "  source_id: orders",
                    "  loader: tests.fixtures.mock_loaders.mock_loader",
                    "  fields:",
                    "    order_id: {extract: order_id}",
                    "sources: {}",
                    "resources:",
                    "  files:",
                    "    detail_csv: {kind: %s, path: ./out}" % kind,
                    "outputs:",
                    "  - name: detail",
                    "    to: {file: detail_csv}",
                    "    write: {header_fields_output_by: field_id}",
                    "    fields: [order_id]",
                    "",
                ]
            )
        )

    for header_by in header_by_values:
        _load_ok(
            "\n".join(
                [
                    "name: demo",
                    "main_source:",
                    "  source_id: orders",
                    "  loader: tests.fixtures.mock_loaders.mock_loader",
                    "  fields:",
                    "    order_id: {extract: order_id}",
                    "sources: {}",
                    "resources:",
                    "  files:",
                    "    detail_csv: {kind: csv_file, path: ./out}",
                    "outputs:",
                    "  - name: detail",
                    "    to: {file: detail_csv}",
                    "    write: {header_fields_output_by: %s}" % header_by,
                    "    fields: [order_id]",
                    "",
                ]
            )
        )


def test_schema_enums_match_runtime_validation_for_books_header_fields_output_by() -> None:
    schema = build_demand_schema()
    output_write_header_by_values = _enum(schema, "definitions", "output_write", "properties", "header_fields_output_by")

    for header_by in output_write_header_by_values:
        _load_ok(
            "\n".join(
                [
                    "name: demo",
                    "main_source:",
                    "  source_id: orders",
                    "  loader: tests.fixtures.mock_loaders.mock_loader",
                    "  fields:",
                    "    order_id: {extract: order_id, name: 订单ID}",
                    "sources: {}",
                    "resources:",
                    "  books:",
                    "    report: {kind: xlsx_file, path: ./out}",
                    "outputs:",
                    "  - name: detail",
                    "    to: {book: report, sheet: Detail}",
                    "    write: {header_fields_output_by: %s}" % header_by,
                    "    fields: [order_id]",
                    "",
                ]
            )
        )


def test_schema_enums_match_runtime_validation_for_outputs_aggregate_rank_and_overflow() -> None:
    schema = build_demand_schema()
    distinct_overflow = _enum(schema, "definitions", "output_aggregate", "properties", "distinct_on_overflow")

    agg_fields = schema["definitions"]["output_aggregate"]["properties"]["fields"]["additionalProperties"]["oneOf"]
    dense_rank = next(item["properties"]["dense_rank"] for item in agg_fields if "dense_rank" in item.get("properties", {}))
    order_enum_raw = dense_rank["properties"]["order"]["enum"]
    assert isinstance(order_enum_raw, list)
    order_enum = [str(x) for x in order_enum_raw]
    top_k_mode_enum_raw = dense_rank["properties"]["top_k_mode"]["enum"]
    assert isinstance(top_k_mode_enum_raw, list)
    top_k_mode_enum = [str(x) for x in top_k_mode_enum_raw]

    for value in distinct_overflow:
        _load_ok(
            "\n".join(
                [
                    "name: demo",
                    "main_source:",
                    "  source_id: orders",
                    "  loader: tests.fixtures.mock_loaders.mock_loader",
                    "  fields:",
                    "    order_id: {extract: order_id}",
                    "sources: {}",
                    "resources:",
                    "  files:",
                    "    detail_csv: {kind: csv_file, path: ./out}",
                    "outputs:",
                    "  - name: agg",
                    "    to: {file: detail_csv}",
                    "    aggregate:",
                    "      group_by: [order_id]",
                    "      distinct_on_overflow: %s" % value,
                    "      fields:",
                    "        cnt: {count: {}}",
                    "",
                ]
            )
        )

    for value in order_enum:
        _load_ok(
            "\n".join(
                [
                    "name: demo",
                    "main_source:",
                    "  source_id: orders",
                    "  loader: tests.fixtures.mock_loaders.mock_loader",
                    "  fields:",
                    "    order_id: {extract: order_id}",
                    "sources: {}",
                    "resources:",
                    "  files:",
                    "    detail_csv: {kind: csv_file, path: ./out}",
                    "outputs:",
                    "  - name: agg",
                    "    to: {file: detail_csv}",
                    "    aggregate:",
                    "      group_by: [order_id]",
                    "      fields:",
                    "        cnt: {count: {}}",
                    "        rank: {dense_rank: {by: cnt, order: %s}}" % value,
                    "",
                ]
            )
        )

    for value in top_k_mode_enum:
        parts = [
            "name: demo",
            "main_source:",
            "  source_id: orders",
            "  loader: tests.fixtures.mock_loaders.mock_loader",
            "  fields:",
            "    order_id: {extract: order_id}",
            "sources: {}",
            "resources:",
            "  files:",
            "    detail_csv: {kind: csv_file, path: ./out}",
            "outputs:",
            "  - name: agg",
            "    to: {file: detail_csv}",
            "    aggregate:",
            "      group_by: [order_id]",
            "      fields:",
            "        cnt: {count: {}}",
        ]
        if value == "rows":
            parts.append("        rank: {dense_rank: {by: cnt, top_k: 1, top_k_mode: rows, order_by: [cnt]}}")
        else:
            parts.append("        rank: {dense_rank: {by: cnt, top_k: 1, top_k_mode: %s}}" % value)
        parts.append("")
        _load_ok("\n".join(parts))
