# SSOT / 生成物 / 门禁地图

这页用于把仓库里常见的“**SSOT(事实来源)** → **生成物/注入区块** → **生成入口** → **漂移门禁**”关系集中成一张可查表,避免在 `docs/`、`openspec/`、`agentdev/`、`scripts/` 之间来回猜。

> 原则: 不确定该改哪里时,先找 SSOT；不确定要不要刷新生成物时,先跑 `just qa` 让门禁告诉你缺了哪个入口。

## 1) 文档治理快速规则

- 任何文件名包含 `.gen.` 的文件都是**全文件生成物**: 不手改；修改 SSOT 后跑 `just gen-docs` 或对应 `just gen-*` 入口。
- 任何 `<!-- BEGIN AUTOGEN:<id> -->` / `<!-- END AUTOGEN:<id> -->` 区块内部是**受控注入内容**: 不手改区块内部；修改 SSOT 后跑 `just gen-docs`。

## 2) 常见 SSOT 对照表

| 领域 | SSOT(事实来源) | 生成物/受控输出 | 生成入口(写入) | 漂移/一致性门禁(只检查) |
| --- | --- | --- | --- | --- |
| docs-site 手工页 | `docs/doc/**/*.md`(非 `.gen.`) | `.gen.` 页 + 注入区块 | `just gen-docs` | `uv run python scripts/gen-docs.py --check`、`uv run python scripts/check-doc-governance.py`、`just qa` |
| OpenSpec 规范 | `openspec/specs/**/spec.md` | 站内索引/摘要(部分为 `.gen.`) | `just gen-docs`(如涉及站内生成页) | `just openspec-check`、`just qa` |
| OpenSpec 变更(正式) | `openspec/changes/<active>/` | 归档后的 change | `openspec sync` / `openspec archive` | `just openspec-check`、`just qa` |
| OpenSpec 脱敏规则 | `openspec/sanitize_rules.yaml` | (无) | `just openspec-sanitize CONFIRM=YES`(一般只在发布/共享前需要) | `just openspec-check`(默认 dry-run) |
| YAML DSL schema | `src/scalim/dsl/yaml_dsl/schema_dsl/**` | `src/scalim/dsl/yaml_dsl/schema/*.gen.json` | `just gen-yaml-dsl-schema` | `just qa`(包含 schema drift check) |
| Agent Skill (YAML DSL) | schema + CLI + specs + canonical example | `agentdev/skills/scalim-yaml-dsl/references/**/*.gen.*` + manifest | `just gen-agent-skill` | `just validate-agent-skill`、`just qa` |
| notebooks 示例回归 | `notebooks/marimo/**` | `notebooks/marimo/marimo_coverage.gen.toon` | `just gen-marimo-coverage` | `just marimo-coverage-drift-check`、`just examples`、`just qa` |
| 项目常量 | `pyproject.toml` | `src/scalim/_project_constants.py` | `just gen-project-constants` | `uv run python scripts/gen-project-constants.py --check`、`just qa` |

## 3) 最常用入口(建议记住这三个)

- `just qa`: 最终验收入口(含 lint/tests + 漂移门禁 + OpenSpec check 等)
- `just gen`: 刷新“所有受控生成物”的统一入口(更偏贡献者/重构场景)
- `just gen-docs`: 只刷新 docs-site 的 `.gen.*` 与注入区块(改文档/规范摘要时常用)
