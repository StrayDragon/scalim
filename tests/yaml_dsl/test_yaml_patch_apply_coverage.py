import pytest

from scalim.dsl.yaml_dsl._internal import patch_apply as patch_apply_mod
from scalim.dsl.yaml_dsl.workflow import ScalimWorkflowConfigError


def test_yaml_patch_apply_as_required_non_empty_str_cover_branches() -> None:
    with pytest.raises(ScalimWorkflowConfigError, match=r"p must be a non-empty string") as exc_info:
        _ = patch_apply_mod.as_required_non_empty_str(1, path="p")  # noqa: SLF001
    assert exc_info.value.path == "p"

    with pytest.raises(ScalimWorkflowConfigError, match=r"p must be a non-empty string") as exc_info:
        _ = patch_apply_mod.as_required_non_empty_str("   ", path="p")  # noqa: SLF001
    assert exc_info.value.path == "p"

    assert patch_apply_mod.as_required_non_empty_str(" a ", path="p") == "a"  # noqa: SLF001
