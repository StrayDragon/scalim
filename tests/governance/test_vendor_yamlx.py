from scalim.vendor.yamlx import yaml as vendored_yaml


def test_yamlx_yaml_is_vendored() -> None:
    assert isinstance(getattr(vendored_yaml, "__file__", None), str)
    assert "/scalim/vendor/yamlx/yaml/" in str(vendored_yaml.__file__).replace("\\", "/")
    assert vendored_yaml.safe_load("a: 1\n") == {"a": 1}


def test_yamlx_ruamel_yaml_is_vendored() -> None:
    from scalim.vendor.yamlx.ruamel import yaml as vendored_ruamel_yaml

    assert isinstance(getattr(vendored_ruamel_yaml, "__file__", None), str)
    assert "/scalim/vendor/yamlx/ruamel/yaml/" in str(vendored_ruamel_yaml.__file__).replace("\\", "/")

    import ruamel.yaml as imported_ruamel_yaml

    assert imported_ruamel_yaml is vendored_ruamel_yaml

    y = vendored_ruamel_yaml.YAML(typ="safe")
    assert y.load("a: 1\n") == {"a": 1}
