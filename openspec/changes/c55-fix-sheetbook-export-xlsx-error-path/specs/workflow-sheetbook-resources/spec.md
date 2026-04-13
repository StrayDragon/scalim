# workflow-sheetbook-resources (delta) Specification

## MODIFIED Requirements

### Requirement: xlsx_memory export_xlsx errors MUST point to the authoring surface config path

When preparing `xlsx_memory` final export (`export_xlsx`) and related versioned output roots, runtime errors that are attributable to `export_xlsx.path` MUST report an actionable configuration path:

- `ScalimWorkflowConfigError.path` MUST point to `workflow.resources.books.<book_id>.export_xlsx.path`
- The message MAY include internal resource hints (e.g. `resource_type=sheetbook`) but MUST NOT replace the user-facing config path

#### Scenario: output root preparation error reports export_xlsx.path
- **GIVEN** a workflow uses `books.<book_id>.kind=xlsx_memory` with `export_xlsx.path`
- **WHEN** preparing the versioned output root fails (e.g. due to permission error or invalid path)
- **THEN** the raised `ScalimWorkflowConfigError` MUST include `path=workflow.resources.books.<book_id>.export_xlsx.path`
