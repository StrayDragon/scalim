# language: zh-CN
# capability: governance-docs-site
# purpose: 定义仓库内文档站点的范围与组织规则：使用 Zensical（兼容 MkDocs 的配置格式）构建站点，以 `docs/doc/` 作为唯一文档真源，避免将规范、审计报告等纳入站点。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: governance-docs-site

  @req:r48 @human
  场景: Documentation site is properly configured
    - The system MUST provide a Zensical configuration and treat `docs/doc/` as the canonical documentation root.

  @req:r292 @human
  场景: Site scope excludes non-manual content
    - The system MUST exclude third-party artifacts and non-manual content (specs, audit reports) from the documentation site. Repository-owned generated docs MAY be included if drift-checked.

  @req:r416 @human
  场景: Legacy docs are migrated and removed
    - The system MUST migrate reorganized legacy docs into the canonical documentation root and remove originals to avoid duplicate sources of truth.

  @req:r511 @human
  场景: Tutorial entry page for demo_big_data_report
    - The system MUST provide a discoverable tutorial entry page under `docs/doc/` that links to the marimo tutorial, `just examples` command, and YAML DSL canonical example. The page MUST declare doc governance boundaries (hand-maintained vs generated content, and CI gates).

  @req:r588 @human
  场景: YAML DSL manual pages reflect current implementation
    - The system MUST ensure YAML DSL manual pages stay consistent with implementation to avoid “docs say X but code rejects it” drift. Manual pages MUST NOT present removed syntax as valid and MUST accurately describe current imports/outputs behavior. Key manual pages include: syntax reference, capability matrix, and user guide. Manual pages MUST: - NOT recommend removed workbook container output syntax - Clarify legacy `outputs.*.container` removal and current CSV output binding method - Describe Excel output binding through resources.books - Accurately describe imports/$import path resolution without conflicting with implementation
  @req:r48 @human
  场景: build-succeeds
    - 必须成立：当 a developer runs the docs build command；那么 the build MUST complete successfully
    当 a developer runs the docs build command
    那么 the build MUST complete successfully

  @req:r48 @human
  场景: docs-root-is-configured
    - 必须成立：当 the documentation site is configured；那么 the configured docs directory MUST resolve to the canonical documentation root
    当 the documentation site is configured
    那么 the configured docs directory MUST resolve to the canonical documentation root
  @req:r292 @human
  场景: site-content-stays-curated
    - 必须成立：当 the documentation site is built or served；那么 only curated pages and explicitly allowed generated pages are included
    当 the documentation site is built or served
    那么 only curated pages and explicitly allowed generated pages are included
  @req:r416 @human
  场景: old-paths-are-removed
    - 必须成立：当 a reader opens an old file path that has been reorganized；那么 the file MUST no longer exist at the old path
    当 a reader opens an old file path that has been reorganized
    那么 the file MUST no longer exist at the old path
  @req:r511 @human
  场景: entry-page-is-discoverable-from-reading-guide
    - 必须成立：当 a reader opens the reading guide；那么 the document MUST contain a link to the tutorial entry page
    当 a reader opens the reading guide
    那么 the document MUST contain a link to the tutorial entry page

  @req:r511 @human
  场景: entry-page-is-discoverable-from-yaml-dsl-manual
    - 必须成立：当 a reader opens the YAML DSL manual index；那么 the document MUST contain a link to the tutorial entry page
    当 a reader opens the YAML DSL manual index
    那么 the document MUST contain a link to the tutorial entry page
  @req:r588 @human
  场景: user-guide-does-not-recommend-removed-syntax
    - 必须成立：当 a reader follows the user guide outputs examples；那么 the examples MUST NOT include removed workbook container output syntax
    当 a reader follows the user guide outputs examples
    那么 the examples MUST NOT include removed workbook container output syntax

  @req:r588 @human
  场景: manual-describes-legacy-removal-and-current-bindings
    - 必须成立：当 a reader reviews outputs sections；那么 the documentation MUST describe legacy removal and current output binding methods for CSV and Excel
    当 a reader reviews outputs sections
    那么 the documentation MUST describe legacy removal and current output binding methods for CSV and Excel
