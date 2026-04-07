from scalim.dsl.yaml_dsl._internal.config_parsing.validator import ValidationReport


def test_validation_report_warnings_and_ok() -> None:
    report = ValidationReport()

    report.add_warning("warning", path="fields.customer_name")
    warnings = report.warnings()

    assert len(warnings) == 1
    assert warnings[0].severity == "warning"
    assert warnings[0].message == "warning"
    assert warnings[0].path == "fields.customer_name"
    assert report.ok() is True

    report.add_error("error", path="fields.customer_id")

    assert report.ok() is False
    assert len(report.errors()) == 1
