import pytest

from scalim.dsl.yaml_dsl._internal.config_parsing.error_envelope import ScalimYamlValidationError
from scalim.dsl.yaml_dsl._internal.config_parsing.loader import YamlDemandLoader
from scalim.dsl.yaml_dsl._internal.config_parsing.parsers.outputs import ParserOutputsMixin
from scalim.dsl.yaml_dsl.schema_dsl.models import OutputTargetConfig


def _load(yaml_content: str):
    loader = YamlDemandLoader()
    return loader.load_string(yaml_content)


class _OutputsParser(ParserOutputsMixin):
    pass


def test_loader_rejects_legacy_output_key() -> None:
    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
sources: {}
output:
  format: csv
"""
    with pytest.raises(ScalimYamlValidationError) as exc:
        _ = _load(yaml_content)

    assert any("Legacy YAML syntax is not supported: top-level 'output'" in env.message for env in exc.value.errors)


def test_loader_parses_outputs_from_inheritance_and_prunes_fields() -> None:
    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
    channel:
      extract: channel
    extra:
      extract: extra
sources: {}
resources:
  files:
    base_csv: {kind: csv_file, path: ./out}
outputs:
  - name: base
    to: {file: base_csv}
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
    assert config.outputs[1].to is not None
    assert config.outputs[1].to.file == "base_csv"  # to IS inherited

    # required_field_ids comes from outputs fields + where.requires; only these are parsed into config fields
    assert set(config.source_fields.keys()) == {"order_id", "channel"}
    assert "extra" not in config.source_fields


def test_loader_rejects_duplicate_output_name() -> None:
    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
resources:
  files:
    a_csv: {kind: csv_file, path: ./out_a}
    b_csv: {kind: csv_file, path: ./out_b}
outputs:
  - name: dup
    to: {file: a_csv}
    fields: [order_id]
  - name: dup
    to: {file: b_csv}
    fields: [order_id]
"""
    with pytest.raises(ValueError, match="Duplicate output name"):
        _ = _load(yaml_content)


def test_loader_rejects_outputs_from_unknown() -> None:
    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
resources:
  files:
    detail_csv: {kind: csv_file, path: ./out}
outputs:
  - name: child
    from: missing
    to: {file: detail_csv}
    fields: [order_id]
"""
    with pytest.raises(ValueError) as exc:
        _ = _load(yaml_content)

    msg = str(exc.value)
    assert "outputs.child.from points to unknown output: missing" in msg


def test_loader_rejects_outputs_from_cycle() -> None:
    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
resources:
  files:
    detail_csv: {kind: csv_file, path: ./out}
outputs:
  - name: a
    from: b
    to: {file: detail_csv}
    fields: [order_id]
  - name: b
    from: a
    to: {file: detail_csv}
    fields: [order_id]
"""
    with pytest.raises(ValueError, match=r"cycle at 'a'"):
        _ = _load(yaml_content)


def test_loader_rejects_outputs_from_inherits_fields_from_base_without_fields() -> None:
    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
resources:
  files:
    agg_csv: {kind: csv_file, path: ./out_agg}
    child_csv: {kind: csv_file, path: ./out_child}
outputs:
  - name: base_agg
    to: {file: agg_csv}
    aggregate:
      group_by: [order_id]
      fields:
        order_cnt: {count: {field: order_id}}
  - name: child_detail
    from: base_agg
    to: {file: child_csv}
"""
    with pytest.raises(ValueError, match=r"inherits fields from 'base_agg'"):
        _ = _load(yaml_content)


def test_loader_rejects_output_missing_destination_binding() -> None:
    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
outputs:
  - name: detail
    fields: [order_id]
"""
    with pytest.raises(ValueError, match=r"outputs\.0\.to is required; declare exactly one of to\.file or to\.book"):
        _ = _load(yaml_content)


def test_loader_rejects_detail_output_missing_fields() -> None:
    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
resources:
  files:
    detail_csv: {kind: csv_file, path: ./out}
outputs:
  - name: detail
    to: {file: detail_csv}
"""
    with pytest.raises(ScalimYamlValidationError) as exc:
        _ = _load(yaml_content)

    assert any("requires fields for detail output" in env.message for env in exc.value.errors)

    parser = _OutputsParser()
    with pytest.raises(ValueError, match="requires fields for detail output"):
        parser._validate_detail_output_semantics(
            OutputTargetConfig(name="detail"),
            name="detail",
            known_field_ids={"order_id"},
        )


def test_loader_allows_aggregate_output_with_fields_for_layout() -> None:
    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
resources:
  files:
    detail_csv: {kind: csv_file, path: ./out}
outputs:
  - name: by_id
    to: {file: detail_csv}
    aggregate:
      group_by: [order_id]
      fields:
        order_cnt: {count: {field: order_id}}
    fields: [order_id, order_cnt]
"""
    config = _load(yaml_content)
    assert len(config.outputs) == 1
    assert config.outputs[0].aggregate is not None
    assert config.outputs[0].fields == ("order_id", "order_cnt")


def test_loader_rejects_legacy_output_container() -> None:
    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
outputs:
  - name: a
    container: {type: csv, path: ./out}
    fields: [order_id]
"""
    with pytest.raises(ScalimYamlValidationError) as exc:
        _ = _load(yaml_content)
    assert any(env.path == "outputs.0.container" for env in exc.value.errors)
    assert any("container was removed" in env.message for env in exc.value.errors)


def test_loader_rejects_file_output_book_only_write_keys() -> None:
    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
resources:
  files:
    detail_csv: {kind: csv_file, path: ./out}
outputs:
  - name: detail
    to: {file: detail_csv}
    write: {mode: append}
    fields: [order_id]
"""
    with pytest.raises(ScalimYamlValidationError) as exc:
        _ = _load(yaml_content)
    assert any(env.path == "outputs.0.write.mode" for env in exc.value.errors)
    assert any("moved out of output-local write config" in env.message for env in exc.value.errors)
