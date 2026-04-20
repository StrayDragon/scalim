# docs-site Specification

**状态: ✅ 已实现**
## Purpose
定义仓库内文档站点的范围与组织规则：使用 Zensical（兼容 MkDocs 的配置格式）构建站点，以 `docs/doc/` 作为唯一文档真源，避免将规范、审计报告等纳入站点。

## Related Concepts
- Zensical 配置 (zensical.toml)
- 文档根目录 (docs/doc/)
- 构建命令 (justfile)
## Requirements
### Requirement: Documentation site is properly configured
The system MUST provide a Zensical configuration and treat `docs/doc/` as the canonical documentation root.

#### Scenario: Build succeeds
- **WHEN** a developer runs the docs build command
- **THEN** the build MUST complete successfully

#### Scenario: Docs root is configured
- **WHEN** the documentation site is configured
- **THEN** the configured docs directory MUST resolve to the canonical documentation root

### Requirement: Site scope excludes non-manual content
The system MUST exclude third-party artifacts and non-manual content (specs, audit reports) from the documentation site. Repository-owned generated docs MAY be included if drift-checked.

#### Scenario: Site content stays curated
- **WHEN** the documentation site is built or served
- **THEN** only curated pages and explicitly allowed generated pages are included
- **AND** the navigation MUST NOT reference specs or audit reports

### Requirement: Legacy docs are migrated and removed
The system MUST migrate reorganized legacy docs into the canonical documentation root and remove originals to avoid duplicate sources of truth.

#### Scenario: Old paths are removed
- **WHEN** a reader opens an old file path that has been reorganized
- **THEN** the file MUST no longer exist at the old path

### Requirement: Tutorial entry page for demo_big_data_report
The system MUST provide a discoverable tutorial entry page under `docs/doc/` that links to the marimo tutorial, `just examples` command, and YAML DSL canonical example. The page MUST declare doc governance boundaries (hand-maintained vs generated content, and CI gates).

#### Scenario: Entry page is discoverable from reading guide
- **WHEN** a reader opens the reading guide
- **THEN** the document MUST contain a link to the tutorial entry page

#### Scenario: Entry page is discoverable from YAML DSL manual
- **WHEN** a reader opens the YAML DSL manual index
- **THEN** the document MUST contain a link to the tutorial entry page

### Requirement: YAML DSL manual pages reflect current implementation
The system MUST ensure YAML DSL manual pages stay consistent with implementation to avoid “docs say X but code rejects it” drift. Manual pages MUST NOT present removed syntax as valid and MUST accurately describe current imports/outputs behavior.

Key manual pages include: syntax reference, capability matrix, and user guide. Manual pages MUST:
- NOT recommend removed workbook container output syntax
- Clarify legacy `outputs.*.container` removal and current CSV output binding method
- Describe Excel output binding through resources.books
- Accurately describe imports/$import path resolution without conflicting with implementation

#### Scenario: User guide does not recommend removed syntax
- **WHEN** a reader follows the user guide outputs examples
- **THEN** the examples MUST NOT include removed workbook container output syntax

#### Scenario: Manual describes legacy removal and current bindings
- **WHEN** a reader reviews outputs sections
- **THEN** the documentation MUST describe legacy removal and current output binding methods for CSV and Excel
