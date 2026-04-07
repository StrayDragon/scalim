from scalim.dsl.yaml_dsl.init_var_nodes import ScalimInitVarNodeTypeError, ScalimInitVarNodeValueError


def test_init_var_node_error_str_includes_path_and_reason() -> None:
    assert str(ScalimInitVarNodeValueError("bad", path="p")) == "p bad"
    assert str(ScalimInitVarNodeTypeError("bad", path="p")) == "p bad"
