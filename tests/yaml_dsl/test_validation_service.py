import re
import textwrap
from pathlib import Path

import scalim.dsl.yaml_dsl.validation_service as service
from scalim.dsl.yaml_dsl._internal.config_parsing.error_envelope import ErrorEnvelope
from scalim.dsl.yaml_dsl._internal.config_parsing.unknown_fields import UnknownFieldIssue
from scalim.dsl.yaml_dsl._internal.config_parsing.validators.issues import ValidationIssue
from scalim.dsl.yaml_dsl._internal.config_parsing.yaml_load import load_yaml_mapping_text


def _default_demand_schema_path() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "src" / "scalim" / "dsl" / "yaml_dsl" / "schema" / "demand.gen.json"


def _yaml_locations(yaml_text: str):
    loaded, locations, _lines = load_yaml_mapping_text(
        textwrap.dedent(yaml_text).lstrip(),
        source_path="(memory)",
        detect_duplicate_keys=True,
    )
    return loaded, locations


def test_validation_payload_as_dict_includes_optional_paths() -> None:
    payload = service.ValidationPayload(mode="validate", ok=True)
    assert payload.as_dict() == {"mode": "validate", "ok": True, "errors": [], "warnings": []}

    payload = service.ValidationPayload(mode="validate", ok=False, yaml_path="a.yaml", schema_path="schema.json")
    as_dict = payload.as_dict()
    assert as_dict["yaml_path"] == "a.yaml"
    assert as_dict["schema_path"] == "schema.json"

    workflow_payload = service.WorkflowValidationPayload(
        mode="workflow-validate",
        ok=False,
        workflow_yaml_path="workflow.yaml",
        results=[service.ValidationPayload(mode="validate", ok=True)],
    )
    assert workflow_payload.as_dict()["workflow_yaml_path"] == "workflow.yaml"


def test_find_legacy_field_errors_scans_root_sources_fields() -> None:
    yaml_data, locations = _yaml_locations(
        """
        target: 1
        sources:
          s1:
            target: 1
        fields:
          f1:
            target: 1
        """
    )

    errors = service.find_legacy_field_errors(
        yaml_data,
        source_path="(memory)",
        locations=locations,
    )
    assert {item.path for item in errors} == {"target", "sources.s1.target", "fields.f1.target"}
    assert all(item.code == "yaml_legacy_field" for item in errors)
    assert all(item.loc and item.loc.line for item in errors)


def test_find_legacy_field_errors_ignores_non_mapping_sources_fields_and_children() -> None:
    yaml_data, locations = _yaml_locations(
        """
        target: 1
        sources: []
        fields: 1
        """
    )
    errors = service.find_legacy_field_errors(
        yaml_data,
        source_path="(memory)",
        locations=locations,
    )
    assert {item.path for item in errors} == {"target"}

    yaml_data, locations = _yaml_locations(
        """
        sources:
          s1: 1
        fields:
          f1: 1
        """
    )
    errors = service.find_legacy_field_errors(
        yaml_data,
        source_path="(memory)",
        locations=locations,
    )
    assert errors == []


def test_issues_to_rows_handles_multiple_issue_types() -> None:
    _, locations = _yaml_locations("a: 1\nb: 2\n")

    rows = service.issues_to_rows(
        [
            ErrorEnvelope(code="direct", message="direct", source_path="(memory)", path="a", loc=None),
            ValidationIssue(severity="error", message="bad", path="a", suggestions=("hint",)),
            UnknownFieldIssue(path="b", field="bee", suggestions=("b",)),
            "fallback",
        ],
        source_path="(memory)",
        locations=locations,
        default_code="default",
    )

    assert rows[0].code == "direct"
    assert any(item.code == "default" and item.path == "a" for item in rows)
    assert any(item.code == "default" and item.path == "b" and item.suggestions for item in rows)
    assert any(item.code == "default" and item.path == "(root)" for item in rows)


def test_find_removed_outputs_defaults_errors_returns_location_when_available() -> None:
    yaml_data, locations = _yaml_locations(
        """
        name: demo
        outputs_defaults: {book: report}
        """
    )

    errors = service.find_removed_outputs_defaults_errors(
        yaml_data,
        source_path="(memory)",
        locations=locations,
        default_code="e",
    )
    assert len(errors) == 1
    assert errors[0].path == "outputs_defaults"
    assert errors[0].loc and errors[0].loc.line

    errors = service.find_removed_outputs_defaults_errors(
        yaml_data,
        source_path="(memory)",
        locations=None,
        default_code="e",
    )
    assert len(errors) == 1
    assert errors[0].loc is None

    assert (
        service.find_removed_outputs_defaults_errors(
            {"name": "demo"},
            source_path="(memory)",
            locations=locations,
            default_code="e",
        )
        == []
    )


def test_extract_demand_book_ids_handles_non_string_and_blank_keys() -> None:
    assert service.extract_demand_book_ids(None) == set()
    assert service.extract_demand_book_ids({"resources": None}) == set()
    assert service.extract_demand_book_ids({"resources": {"books": None}}) == set()
    assert service.extract_demand_book_ids({"resources": {"books": {}}}) == set()

    ids = service.extract_demand_book_ids({"resources": {"books": {" a ": {}, "": {}, 1: {}}}})
    assert ids == {"a"}


def test_find_demand_book_binding_errors_reports_missing_and_unknown_book_ids() -> None:
    yaml_data, locations = _yaml_locations(
        """
        outputs:
          - container: {kind: csv_file, path: ./out.csv}
          - name: out1
            to: {}
          - name: out2
            to: {book: missing}
          - name: out3
            to: {book: known}
        """
    )

    errors = service.find_demand_book_binding_errors(
        yaml_data,
        source_path="(memory)",
        locations=locations,
        available_book_ids={"known"},
        default_code="e",
    )
    paths = {item.path for item in errors}
    assert paths == {"outputs.1.to.book", "outputs.2.to.book"}
    assert any("Missing outputs to.book binding" in item.message for item in errors)
    assert any("Unknown book id" in item.message for item in errors)


def test_find_demand_book_binding_errors_handles_non_mapping_inputs_and_entries() -> None:
    assert (
        service.find_demand_book_binding_errors(
            None,
            source_path="(memory)",
            locations=None,
            available_book_ids=set(),
            default_code="e",
        )
        == []
    )
    assert service._extract_demand_outputs_book_refs(None) == []

    errors = service.find_demand_book_binding_errors(
        {
            "outputs": [
                1,
                {"name": "out1", "to": 1},
                {"name": "out2"},
            ]
        },
        source_path="(memory)",
        locations=None,
        available_book_ids=set(),
        default_code="e",
    )
    assert {item.path for item in errors} == {"outputs.1.to.book", "outputs.2.to.book"}


def test_find_retry_enabled_missing_should_retry_errors_reports_all_scopes() -> None:
    yaml_data, locations = _yaml_locations(
        """
        retry: {enabled: true}
        main_source:
          retry: {enabled: true, should_retry: ""}
        sources:
          s1:
            retry: {enabled: true, should_retry: " "}
          s2: 1
          s3:
            retry: {enabled: true, should_retry: "ok"}
        """
    )

    errors = service.find_retry_enabled_missing_should_retry_errors(
        yaml_data,
        source_path="(memory)",
        locations=locations,
        default_code="e",
    )
    assert {item.path for item in errors} == {"retry.should_retry", "main_source.retry.should_retry", "sources.s1.retry.should_retry"}


def test_find_retry_enabled_missing_should_retry_errors_ignores_non_mapping_and_disabled_retry() -> None:
    assert service.find_retry_enabled_missing_should_retry_errors(None, source_path="(memory)", locations=None, default_code="e") == []

    yaml_data, locations = _yaml_locations(
        """
        retry: {enabled: false}
        main_source: 1
        sources: []
        """
    )
    errors = service.find_retry_enabled_missing_should_retry_errors(
        yaml_data,
        source_path="(memory)",
        locations=locations,
        default_code="e",
    )
    assert errors == []


def test_validation_service_demand_yaml_parse_error_is_wrapped(tmp_path: Path) -> None:
    schema_path = _default_demand_schema_path()
    assert schema_path.exists()

    result = service.validate_demand_text(
        "name: [\n",
        yaml_path=tmp_path / "bad.yaml",
        schema_path=schema_path,
    )
    assert result.payload.ok is False
    assert any(item.code == "yaml_parse_error" for item in result.payload.errors)


def test_validation_service_demand_import_expansion_error_is_wrapped(tmp_path: Path) -> None:
    schema_path = _default_demand_schema_path()
    assert schema_path.exists()

    result = service.validate_demand_text(
        """
name: demo
main_source:
  $import: missing
""".lstrip(),
        yaml_path=tmp_path / "import.yaml",
        schema_path=schema_path,
    )
    assert result.payload.ok is False
    assert any(item.code == "yaml_import_expansion_error" for item in result.payload.errors)


def test_validation_service_demand_import_expansion_success_can_validate(tmp_path: Path) -> None:
    schema_path = _default_demand_schema_path()
    assert schema_path.exists()

    fragment_path = tmp_path / "fragment.yaml"
    fragment_path.write_text(
        """
fields:
  profit:
    compute: "1"
""".lstrip(),
        encoding="utf-8",
    )

    result = service.validate_demand_text(
        """
name: demo
imports:
  common: ./fragment.yaml
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
sources: {}
fields:
  $import: common.fields
""".lstrip(),
        yaml_path=tmp_path / "demand.yaml",
        schema_path=schema_path,
        allowed_yaml_roots=[tmp_path],
    )
    assert result.payload.ok is True


def test_validation_service_demand_file_schema_missing_and_not_found_and_read_error(tmp_path: Path) -> None:
    schema_path = tmp_path / "missing.gen.json"

    result = service.validate_demand_file(tmp_path / "missing.yaml", schema_path=schema_path)
    assert result.payload.ok is False
    assert any(item.code == "schema_file_not_found" for item in result.payload.errors)

    schema_path = _default_demand_schema_path()
    assert schema_path.exists()

    missing = tmp_path / "missing.yaml"
    result = service.validate_demand_file(missing, schema_path=schema_path)
    assert result.payload.ok is False
    assert any(item.code == "yaml_file_not_found" for item in result.payload.errors)

    bad_dir = tmp_path / "dir"
    bad_dir.mkdir()
    result = service.validate_demand_file(bad_dir, schema_path=schema_path)
    assert result.payload.ok is False
    assert any(item.code == "yaml_file_read_error" for item in result.payload.errors)


def test_validation_service_workflow_schema_missing_returns_single_result(tmp_path: Path) -> None:
    workflow_path = tmp_path / "workflow.yaml"
    result = service.validate_workflow_text(
        "workflow: {runs: []}\n",
        yaml_path=workflow_path,
        schema_path=tmp_path / "missing.gen.json",
        path_aliases=None,
        allowed_yaml_roots=None,
    )
    assert result.payload.ok is False
    assert len(result.payload.results) == 1
    assert any(item.code == "schema_file_not_found" for item in result.workflow_payload.errors)


def test_validation_service_workflow_yaml_parse_error_is_wrapped(tmp_path: Path) -> None:
    schema_path = _default_demand_schema_path()
    assert schema_path.exists()

    result = service.validate_workflow_text(
        "workflow: [\n",
        yaml_path=tmp_path / "workflow.yaml",
        schema_path=schema_path,
        path_aliases=None,
        allowed_yaml_roots=None,
    )
    assert result.payload.ok is False
    assert any(item.code == "yaml_parse_error" for item in result.workflow_payload.errors)


def test_validation_service_workflow_unexpected_exception_is_wrapped(tmp_path: Path, monkeypatch) -> None:
    schema_path = _default_demand_schema_path()
    assert schema_path.exists()

    def _boom(_yaml: object) -> object:
        raise RuntimeError("boom")

    monkeypatch.setattr(service, "load_workflow_config_from_mapping", _boom)

    result = service.validate_workflow_text(
        "workflow: {runs: []}\n",
        yaml_path=tmp_path / "workflow.yaml",
        schema_path=schema_path,
        path_aliases=None,
        allowed_yaml_roots=None,
    )
    assert result.payload.ok is False
    assert any("Unexpected error" in item.message for item in result.workflow_payload.errors)


def test_validation_service_workflow_demand_file_not_found_yields_two_results(tmp_path: Path) -> None:
    schema_path = _default_demand_schema_path()
    assert schema_path.exists()

    workflow_path = tmp_path / "workflow.yaml"
    result = service.validate_workflow_text(
        """
workflow:
  runs:
    - id: r1
      demand: ./missing.yaml
""".lstrip(),
        yaml_path=workflow_path,
        schema_path=schema_path,
        path_aliases=None,
        allowed_yaml_roots=[tmp_path],
    )
    assert result.payload.ok is False
    assert len(result.payload.results) == 2
    assert any(item.code == "demand_file_not_found" for item in result.workflow_payload.errors)
    demand_payload = result.payload.results[1]
    assert any(item.code == "yaml_file_not_found" for item in demand_payload.errors)


def test_validation_service_workflow_file_reads_and_delegates(tmp_path: Path) -> None:
    schema_path = _default_demand_schema_path()
    assert schema_path.exists()

    demand_path = tmp_path / "demand.yaml"
    demand_path.write_text(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
""".lstrip(),
        encoding="utf-8",
    )

    workflow_path = tmp_path / "workflow.yaml"
    workflow_path.write_text(
        """
workflow:
  runs:
    - id: r1
      demand: ./demand.yaml
""".lstrip(),
        encoding="utf-8",
    )

    result = service.validate_workflow_file(
        workflow_path,
        schema_path=schema_path,
        path_aliases=None,
        allowed_yaml_roots=[tmp_path],
    )
    assert result.payload.ok is True


def test_validation_service_demand_schema_missing_returns_payload(tmp_path: Path) -> None:
    yaml_path = tmp_path / "demo.yaml"
    schema_path = tmp_path / "missing.gen.json"

    result = service.validate_demand_text(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
""".lstrip(),
        yaml_path=yaml_path,
        schema_path=schema_path,
    )

    assert result.payload.ok is False
    assert result.payload.schema_path == str(schema_path)
    assert result.payload.errors
    assert result.payload.errors[0].code == "schema_file_not_found"
    assert re.search(r"Schema 文件不存在", result.payload.errors[0].message)


def test_validation_service_workflow_semantic_error_is_wrapped(tmp_path: Path) -> None:
    schema_path = _default_demand_schema_path()
    assert schema_path.exists()

    workflow_path = tmp_path / "workflow.yaml"
    result = service.validate_workflow_text(
        """
workflow:
  runs:
    - id: r1
      demand: ./demand.yaml
      writes:
        - csv_append:
            csv: out
            output: missing_output
""".lstrip(),
        yaml_path=workflow_path,
        schema_path=schema_path,
        path_aliases=None,
        allowed_yaml_roots=None,
    )

    assert result.payload.ok is False
    assert len(result.payload.results) == 1
    assert any(item.path == "workflow.runs.0.writes" for item in result.workflow_payload.errors)


def test_validation_service_workflow_demand_path_alias_error_produces_two_results(tmp_path: Path) -> None:
    schema_path = _default_demand_schema_path()
    assert schema_path.exists()

    workflow_path = tmp_path / "workflow.yaml"
    result = service.validate_workflow_text(
        """
workflow:
  runs:
    - id: r1
      demand: UnknownAlias:/demand.yaml
""".lstrip(),
        yaml_path=workflow_path,
        schema_path=schema_path,
        path_aliases=None,
        allowed_yaml_roots=None,
    )

    assert result.payload.ok is False
    assert len(result.payload.results) == 2

    workflow_payload = result.payload.results[0]
    assert workflow_payload.mode == "workflow-validate"
    assert any(item.path == "workflow.runs.0.demand" for item in workflow_payload.errors)

    demand_payload = result.payload.results[1]
    assert demand_payload.mode == "validate"
    assert demand_payload.yaml_path == "UnknownAlias:/demand.yaml"
    assert any(item.code == "demand_path_resolve_failed" for item in demand_payload.errors)


def test_validation_service_demand_semantic_errors_match_validator_paths(tmp_path: Path) -> None:
    schema_path = _default_demand_schema_path()
    assert schema_path.exists()

    yaml_path = tmp_path / "demand.yaml"
    result = service.validate_demand_text(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  unknown_field: 1
""".lstrip(),
        yaml_path=yaml_path,
        schema_path=schema_path,
    )

    assert result.payload.ok is False
    assert any(item.path == "main_source.unknown_field" and item.loc and item.loc.line for item in result.payload.errors)
