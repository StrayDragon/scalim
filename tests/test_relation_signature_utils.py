from scalim.utils.relation_signature import normalize_key_field


def test_normalize_key_field_converts_list_to_tuple() -> None:
    assert normalize_key_field(["a", "b"]) == ("a", "b")
