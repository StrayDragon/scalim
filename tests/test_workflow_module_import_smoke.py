def test_workflow_ctx_and_artifacts_modules_are_importable() -> None:
    from scalim.workflow import artifacts as artifacts_mod
    from scalim.workflow import ctx as ctx_mod
    from scalim.workflow import execute as execute_mod

    assert ctx_mod.WorkflowCtxStore is execute_mod.WorkflowCtxStore
    assert artifacts_mod.WorkflowArtifactsDirectory is execute_mod.WorkflowArtifactsDirectory


def test_workflow_runtime_config_error_str_formatting_without_path() -> None:
    from scalim.workflow.errors import ScalimWorkflowConfigError

    assert str(ScalimWorkflowConfigError("msg")) == "msg"
