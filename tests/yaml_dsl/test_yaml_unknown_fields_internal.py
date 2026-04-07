from scalim.dsl.yaml_dsl._internal.config_parsing import unknown_fields as uf


def test_unknown_fields_private_helpers_cover_edge_branches() -> None:
    assert uf._value_schema_types(None) == frozenset({"null"})  # noqa: SLF001
    assert uf._value_schema_types(True) == frozenset({"boolean"})  # noqa: SLF001
    assert uf._value_schema_types(1) == frozenset({"integer", "number"})  # noqa: SLF001
    assert uf._value_schema_types(1.0) == frozenset({"number"})  # noqa: SLF001
    assert uf._value_schema_types("x") == frozenset({"string"})  # noqa: SLF001
    assert uf._value_schema_types({}) == frozenset({"object"})  # noqa: SLF001
    assert uf._value_schema_types(object()) == frozenset()  # noqa: SLF001

    assert uf._schema_type_set({"type": ["string", "number"]}) == frozenset({"string", "number"})  # noqa: SLF001
    assert uf._schema_accepts_value({"type": "string"}, object()) is True  # noqa: SLF001

    # oneOf/anyOf 没有 dict 分支: 直接返回空列表
    assert uf._maybe_select_variant_branches({"oneOf": [1, 2]}, {}, {}) == []  # noqa: SLF001
    # 所有分支都被类型过滤掉时,回退到原 candidates
    assert uf._maybe_select_variant_branches({"oneOf": [{"type": "string"}]}, {}, {}) == [{"type": "string"}]  # noqa: SLF001
    # value 非 dict 且 filtered>1 的分支
    schema = {"anyOf": [{"type": "array"}, {"type": "array"}]}
    assert len(uf._maybe_select_variant_branches(schema, {}, [])) == 2  # noqa: SLF001


def test_unknown_fields_internal_dedup_and_schema_union_helpers() -> None:
    # 覆盖 `_iter_relevant_schemas` 去重分支: same schema 在 variants 与 anyOf 分支重复出现
    shared = {"type": "object", "properties": {}, "additionalProperties": False}
    schema = {
        "type": "object",
        "allOf": [shared, {"anyOf": [shared]}],
        "properties": {},
        "additionalProperties": False,
    }
    issues = uf.find_unknown_fields({"x": 1}, schema)
    assert issues

    # 覆盖 `_collect_object_schema_info` 中 properties value 非 dict 的 ignore 分支
    schema_bad_props = {"type": "object", "properties": {"x": 1}, "additionalProperties": False}
    bad_issues = uf.find_unknown_fields({"x": 1}, schema_bad_props)
    assert bad_issues and bad_issues[0].path == "x"

    # 覆盖 `additional_schema` anyOf 合并分支(多个 additionalProperties schema)
    additional_schema = {"type": "object", "properties": {}, "additionalProperties": False}
    dynamic_1 = {"type": "object", "additionalProperties": additional_schema}
    dynamic_2 = {"type": "object", "additionalProperties": additional_schema}
    union_schema = {"allOf": [dynamic_1, dynamic_2]}
    known_keys, prop_map, additional = uf._collect_object_schema_info(  # noqa: SLF001
        {"k": {}},
        union_schema,
        union_schema,
    )
    assert known_keys is None
    assert prop_map == {}
    assert additional is not None and "anyOf" in additional

    # 覆盖 `_resolve_array_item_schema` 的 items(list)+additionalItems 分支与 items anyOf 合并分支
    item_a = {"type": "object", "properties": {"a": {"type": "string"}}, "additionalProperties": False}
    item_b = {"type": "object", "properties": {"b": {"type": "string"}}, "additionalProperties": False}
    array_1 = {"type": "array", "items": [item_a], "additionalItems": item_b}
    array_2 = {"type": "array", "items": item_b}
    root = {"allOf": [array_1, array_2]}
    merged = uf._resolve_array_item_schema(root, root, 1, [{}, {}])  # noqa: SLF001
    assert merged is not None and "anyOf" in merged

    selected = uf._resolve_array_item_schema(array_1, array_1, 0, [{}])  # noqa: SLF001
    assert selected == item_a
