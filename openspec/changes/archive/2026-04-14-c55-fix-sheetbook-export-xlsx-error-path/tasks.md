## 1. Align Error Path Semantics

- [ ] 1.1 Identify the failing runtime path(s) where `xlsx_memory` export root preparation errors produce an incorrect/ambiguous `ScalimWorkflowConfigError.path`.
- [ ] 1.2 Update the workflow runtime to ensure `ScalimWorkflowConfigError.path` points to the authoring surface key: `workflow.resources.books.<book_id>.export_xlsx.path`.
- [ ] 1.3 If needed, add a small internal hint in the error message (e.g. `resource_type=sheetbook`) without changing the user-facing `path`.

## 2. Tests

- [ ] 2.1 Add a regression test for `build_workflow_resource_defs` that forces an `OSError` during export root preparation for a `sheetbook` resource and asserts `exc.path == "workflow.resources.books.<book_id>.export_xlsx.path"`.
- [ ] 2.2 Keep the test deterministic by monkeypatching `versioned_outputs.ensure_output_root_layout` (or the first failing filesystem call) to raise a controlled exception.

## 3. QA / Governance

- [ ] 3.1 Run targeted tests: `uv run pytest tests/workflow/ -q`.
- [ ] 3.2 Run `just qa` to confirm all gates pass.
- [ ] 3.3 Run `just openspec-check` to validate OpenSpec artifacts.

## 4. SSOT / Generated Artifacts

- [ ] 4.1 Confirm no generated artifacts (`*.gen.*`) are modified; SSOT is runtime code + tests, validated by `just qa`.
