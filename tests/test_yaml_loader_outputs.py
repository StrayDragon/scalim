import pytest

from scalim.dsl.by_yaml.config_parsing.errors import ConfigValidationError
from scalim.dsl.by_yaml.config_parsing.loader import YamlDemandLoader


def _load(yaml_content: str):
    loader = YamlDemandLoader()
    return loader.load_string(yaml_content)


def test_loader_rejects_legacy_output_key() -> None:
    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
sources: {}
output:
  format: csv
"""
    with pytest.raises(ConfigValidationError) as exc:
        _ = _load(yaml_content)

    assert any("Legacy YAML syntax is not supported: top-level 'output'" in msg for msg in exc.value.errors)


def test_loader_parses_outputs_from_inheritance_and_prunes_fields() -> None:
    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
    channel:
      extract: channel
    extra:
      extract: extra
sources: {}
outputs:
  - name: base
    container: {type: csv, path: ./base.csv}
    fields: [order_id]
    where: "channel == 'direct'"
  - name: child
    from: base
"""
    config = _load(yaml_content)

    assert len(config.outputs) == 2
    assert config.outputs[0].name == "base"
    assert config.outputs[0].where == "channel == 'direct'"
    assert config.outputs[0].requires == ("channel",)

    assert config.outputs[1].name == "child"
    assert config.outputs[1].fields == ("order_id",)
    assert config.outputs[1].where is None  # where is NOT inherited
    assert config.outputs[1].requires == ()
    assert config.outputs[1].container is not None
    assert config.outputs[1].container.path == "./base.csv"  # container IS inherited

    # required_field_ids comes from outputs fields + where.requires; only these are parsed into config fields
    assert set(config.source_fields.keys()) == {"order_id", "channel"}
    assert "extra" not in config.source_fields


def test_loader_rejects_duplicate_output_name() -> None:
    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
outputs:
  - name: dup
    container: {type: csv, path: ./a.csv}
    fields: [order_id]
  - name: dup
    container: {type: csv, path: ./b.csv}
    fields: [order_id]
"""
    with pytest.raises(ValueError, match="Duplicate output name"):
        _ = _load(yaml_content)


def test_loader_rejects_outputs_from_unknown() -> None:
    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
outputs:
  - name: child
    from: missing
    container: {type: csv, path: ./out.csv}
    fields: [order_id]
"""
    with pytest.raises(ValueError, match=r"points to unknown output"):
        _ = _load(yaml_content)


def test_loader_rejects_outputs_from_cycle() -> None:
    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
outputs:
  - name: a
    from: b
    container: {type: csv, path: ./out.csv}
    fields: [order_id]
  - name: b
    from: a
    container: {type: csv, path: ./out.csv}
    fields: [order_id]
"""
    with pytest.raises(ValueError, match="cycle"):
        _ = _load(yaml_content)


def test_loader_rejects_output_missing_container() -> None:
    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
outputs:
  - name: detail
    fields: [order_id]
"""
    with pytest.raises(ValueError, match="missing required container"):
        _ = _load(yaml_content)


def test_loader_rejects_detail_output_missing_fields() -> None:
    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
outputs:
  - name: detail
    container: {type: csv, path: ./out.csv}
"""
    with pytest.raises(ValueError, match="requires fields for detail output"):
        _ = _load(yaml_content)


def test_loader_rejects_aggregate_output_with_fields() -> None:
    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
outputs:
  - name: by_id
    container: {type: workbook, path: ./out.xlsx, sheet: Summary}
    fields: [order_id]
    aggregate:
      group_by: [order_id]
      fields:
        order_cnt: {count: {field: order_id}}
"""
    with pytest.raises(ValueError, match="does not allow fields"):
        _ = _load(yaml_content)


def test_loader_rejects_shared_workbook_missing_sheet() -> None:
    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
outputs:
  - name: a
    container: {type: workbook, path: ./out.xlsx, sheet: A}
    fields: [order_id]
  - name: b
    container: {type: workbook, path: ./out.xlsx}
    fields: [order_id]
"""
    with pytest.raises(ValueError, match="Multiple outputs share the same workbook path"):
        _ = _load(yaml_content)


def test_loader_rejects_container_streaming_false() -> None:
    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
outputs:
  - name: detail
    container: {type: csv, path: ./out.csv, streaming: false}
    fields: [order_id]
"""
    with pytest.raises(ValueError, match="streaming must be true"):
        _ = _load(yaml_content)
