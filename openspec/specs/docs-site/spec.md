# docs-site Specification

**状态: ✅ 已实现**
## Purpose
定义仓库内文档站点的范围与组织规则:使用 Zensical(兼容 MkDocs 的 `mkdocs.yml`)构建站点,以 `docs/doc/` 作为唯一文档真源,并避免将 `openspec/specs/**`、`_REPORT/**` 等规范/审计内容纳入站点.

## Related Code (as implemented)
- `mkdocs.yml`
- `docs/doc/`
- `justfile`
## Requirements
### Requirement: Documentation site exists
The system MUST provide an MkDocs-compatible configuration at repository root and allow building a documentation site from repository Markdown sources.

#### Scenario: Build succeeds
- **WHEN** a developer runs the docs build command (Zensical)
- **THEN** the build MUST complete successfully

### Requirement: Canonical docs live under docs/doc
The system MUST treat `docs/doc/` as the canonical location for the organized, final documentation set used by the documentation site.

#### Scenario: Docs root is docs/doc
- **WHEN** the documentation site is configured
- **THEN** the `docs_dir` MUST be `docs/doc`

### Requirement: Generated/third-party artifacts are excluded
The system MUST NOT include auto-generated or third-party Markdown content (for example `.venv/`, `node_modules/`, archived change artifacts) into the documentation site.

#### Scenario: Site content stays curated
- **WHEN** the documentation site is built or served
- **THEN** only curated documentation pages intended for humans are included in the nav and searchable content

### Requirement: Site scope is manuals only
The system MUST scope the documentation site to curated developer/user manual pages and MUST NOT include repository specs or audit reports (for example `openspec/specs/**` and `_REPORT/**`) in the site content root or navigation.

#### Scenario: Specs and reports are out of scope
- **WHEN** the documentation site is built or served
- **THEN** the navigation MUST NOT reference pages sourced from `openspec/specs/**` or `_REPORT/**`

### Requirement: Legacy scattered docs are moved and removed after reorg
The system MUST migrate reorganized legacy Markdown docs into `docs/doc/` and MUST remove the original files to avoid duplicated sources of truth.

#### Scenario: Old paths are removed
- **WHEN** a reader opens an old Markdown file path that has been reorganized
- **THEN** the file MUST no longer exist at the old path (it has been moved under `docs/doc/`)
