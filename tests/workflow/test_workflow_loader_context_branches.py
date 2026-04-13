import scalim.workflow.loaders as loaders_mod


def test_workflow_loader_context_restores_previous_context() -> None:
    if hasattr(loaders_mod._TLS, "ctx"):  # noqa: SLF001
        del loaders_mod._TLS.ctx  # noqa: SLF001

    manager_outer = object()
    manager_inner = object()

    with loaders_mod.workflow_loader_context(  # noqa: SLF001
        workflow_exec_id="exec",
        workflow_node_id="outer",
        visible_producer_node_ids=frozenset(["a"]),
        resource_manager=manager_outer,  # type: ignore[arg-type]
    ):
        outer_ctx = loaders_mod._TLS.ctx  # noqa: SLF001

        with loaders_mod.workflow_loader_context(  # noqa: SLF001
            workflow_exec_id="exec",
            workflow_node_id="inner",
            visible_producer_node_ids=frozenset(["b"]),
            resource_manager=manager_inner,  # type: ignore[arg-type]
        ):
            assert loaders_mod._TLS.ctx.resource_manager is manager_inner  # noqa: SLF001

        assert loaders_mod._TLS.ctx is outer_ctx  # noqa: SLF001

    assert not hasattr(loaders_mod._TLS, "ctx")  # noqa: SLF001
