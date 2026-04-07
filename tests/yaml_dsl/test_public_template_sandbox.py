import pytest

from scalim.dsl.yaml_dsl._public_template_sandbox import validate_public_template_sandbox


def test_validate_public_template_sandbox_rejects_unknown_value() -> None:
    with pytest.raises(ValueError):
        validate_public_template_sandbox("unknown")
