# 文档治理与生成工作流

本仓库将文档分为四类,并要求边界清晰(可机械校验,可在 CI 门禁):

1. **SSOT(事实来源)**: 代码/配置/规范本体(例如 `src/scalim/**`, `pyproject.toml`, `llmanspec/specs/**/spec.md`)
2. **Generated(全文件生成物)**: 文件名包含 `.gen.` 的产物(例如 `*.gen.md/*.gen.json`),禁止手改
3. **Manual(手工页)**: 叙事/教程/排错路径,允许链接到 SSOT/Generated,但不重复大段 reference
4. **Manual + Injected Blocks**: 手工页中的受控注入区块,由生成器按 marker 替换:
   - `<!-- BEGIN AUTOGEN:<id> -->`
   - `<!-- END AUTOGEN:<id> -->`

如果你不确定“某个文档/产物到底该改 SSOT 还是改生成物、要跑哪个生成入口”,先看:

- [SSOT / 生成物 / 门禁地图](ssot-map.md)

## YAML DSL upgrades 的 SSOT

为避免在 docs 与 skill 中重复维护 YAML DSL 的 breaking/migration 说明:

- **SSOT**: `agentdev/skills/scalim-yaml-dsl/references/upgrades/`
- docs-site 页面 `docs/doc/yaml-dsl/upgrades/*.gen.md`（除 `index.md` 外）由 SSOT 自动生成,不单独维护(运行 `just gen-docs`)
- 新增/更新升级指南后跑 `just gen` 以刷新 docs 与 skill 的升级索引/摘要(供 agent 使用)

## 入口命令

- 刷新**所有**受控生成物(贡献者/重构常用): `just gen`
- 刷新 docs 相关受控输出: `just gen-docs`
- 漂移门禁(只检查不写入): `just docs-drift-check` (也会被 `just qa`/CI 覆盖)

## Notebooks (marimo)

notebooks 本体是交互式 demo,但同时也是 **确定性回归入口** 的 SSOT(示例/对拍以 notebooks 的代码与 fixtures 为准):

- 交互式入口(本地): `uv run marimo edit notebooks/marimo/`
- 回归入口(headless/CI): `just examples`（`just qa` 会覆盖）
  - 实际执行入口: `justfile` 的 `examples:` recipe（内联 runner）
  - 覆盖报告(按需生成): `just report-notebooks-coverage`
    - 门禁: `just check-notebooks-coverage`
    - 输出: 每 notebook 的 Tier1 API 入口覆盖 CSV（suite, notebook, covered_pct, covered_modules, missing_modules）

如需把 marimo notebooks 导出为 docs-site 可直接浏览的 HTML(可选),运行:

- `uv run python scripts/export-marimo-to-docs.py`

说明: notebooks 的 HTML 导出不属于 `just gen-docs` 的受控生成物;以 `just examples` / `just check-notebooks-coverage` 的回归口径为准。

## doc_texts 模式(推荐)

当某段文档内容需要与实现保持强同步(但不适合把整页都生成)时,推荐把片段沉淀在“所有者模块”的 `doc_texts.py` 中,
并通过 injected block 注入到站内手工页:

- 例: YAML DSL 的片段 SSOT: `src/scalim/dsl/yaml_dsl/schema_dsl/doc_texts.py`
- 例: 注入目标页: `docs/doc/yaml-dsl/user-guide.md` 中的 `AUTOGEN:*` 区块
- 生成入口: `scripts/gen-docs.py` (统一入口: `just gen-docs`)

新增一个注入片段的最小步骤:

1. 在 owning module 增加/更新 `doc_texts.py` 的片段常量(SSOT)
2. 在目标手工页放置 begin/end markers
3. 把注入逻辑接入 `scripts/gen-docs.py`
4. 运行 `just gen-docs` 并提交生成物
