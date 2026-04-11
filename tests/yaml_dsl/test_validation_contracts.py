import pytest

from scalim.dsl.yaml_dsl import workflow_compile as workflow_compile_mod
from scalim.dsl.yaml_dsl._internal.validation_contracts import validate_excel_sheet_name, validate_output_name
from scalim.dsl.yaml_dsl.runtime import output_composition_yaml as oc_yaml_mod


def test_validate_excel_sheet_name_errors_use_single_template() -> None:
    with pytest.raises(ValueError, match=r"^p: .*Hint:"):
        validate_excel_sheet_name("", path="p")

    with pytest.raises(ValueError, match=r"Excel sheet name is too long.*Hint:"):
        validate_excel_sheet_name("x" * 32, path="p")

    with pytest.raises(ValueError, match=r"invalid characters.*Hint:"):
        validate_excel_sheet_name("A/B", path="p")


def test_validate_output_name_errors_use_single_template() -> None:
    with pytest.raises(ValueError, match=r"^outputs\.\*\.name: .*Hint:"):
        validate_output_name("", path="outputs.*.name")

    with pytest.raises(ValueError, match=r"Invalid identifier.*Hint:"):
        validate_output_name("1bad", path="outputs.*.name")

    validate_output_name("good_name_1", path="outputs.*.name")


def test_validate_excel_sheet_name_is_shared_across_workflow_and_runtime_entrypoints() -> None:
    with pytest.raises(ValueError) as exc_info:
        workflow_compile_mod._validate_excel_sheet_name("", path="p")  # noqa: SLF001
    with pytest.raises(ValueError) as exc_info_2:
        oc_yaml_mod._validate_excel_sheet_name("", path="p")  # noqa: SLF001

    assert str(exc_info.value) == str(exc_info_2.value)
