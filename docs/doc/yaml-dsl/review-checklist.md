# YAML DSL 提案审核清单

本页用于评审/编写 YAML DSL 相关 llmanspec 变更时的统一 checklist,避免反复在各个专题提案中重复解释主线原则与边界。

上位原则 SSOT: `llmanspec/specs/yaml-dsl-mainline-principles/spec.md`。

## 0) 必须遵守的主线原则(硬约束)

- **禁止并行版本**: 不引入 `dsl_version`;不通过 CLI/schema/modeline 选择并行 DSL 版本。
- **禁止并行实现链路**: 不维护并行 parser/validator/schema 产物来长期承载旧写法。
- **分层清晰**:
  - `YAML = authoring`(可移植、可读、稳定的配置面)
  - `Python/CLI = runtime policy`(环境/性能预算/集成策略/diagnostics 等)
- **KV-first**: 需要稳定 ID、引用、复用的结构优先 mapping;只有顺序具业务语义时才引入 list。
- **workflow 小而声明式**: workflow 聚焦 orchestration;不得扩张为 imports/片段组合系统(禁止 workflow imports expansion)。

## 1) 提案本体检查(proposal/design/specs/tasks)

- proposal 是否明确:
  - 变更边界(包含/不包含)
  - 破坏性变更与迁移路径(如有)
  - 文档/生成物边界(哪些是 SSOT,哪些是 `.gen.*` / `AUTOGEN` 注入区块)
- design 是否收敛:
  - schema/runtime/docs 三者边界与对齐策略
  - 生成入口与漂移门禁(`just gen-docs`/`just gen-yaml-dsl-schema`/`just qa`)
- specs 是否提供可验证的 Requirements/Scenarios(避免“只有叙述没有口径”)。
- tasks 是否覆盖:
  - 代码实现 + 测试
  - schema 生成(如涉及)与 drift gate
  - docs/skill/notebooks(如涉及)与生成/验收口径
  - `just llmanspec-check` 与 `just qa`

## 1.5) 专题拆分与依赖顺序(参考)

为避免“总提案 + 细节杂糅”反复漂移,YAML DSL 相关变更默认按以下链路拆分推进(仅写 `<name>`;实际 active change 目录名会带 `c<priority>-` 前缀):

- `yaml-dsl-mainline-principles`(上位原则)
- `yaml-dsl-schema-workflow-alignment`(基础可信度)
- `yaml-dsl-observability-out-of-yaml`(方向明确的专题)
- `yaml-dsl-runtime-policy-boundary` / `yaml-dsl-write-policy-and-output-extras` / `yaml-dsl-demand-imports-scope`(边界型专题)
- `yaml-dsl-lsp`(编辑器/LSP 语义边界与 tooling 特例接口)

## 2) 实现影响面检查(避免只改单点)

当变更触及 DSL surface 时,至少检查并对齐:

- schema: `src/scalim/dsl/yaml_dsl/schema_dsl/**` → 生成物 `src/scalim/dsl/yaml_dsl/schema/*.gen.json`(仅通过 `just gen-yaml-dsl-schema` 刷新)
- parser/validator: `src/scalim/dsl/yaml_dsl/_internal/config_parsing/**`
- runtime conversion/compile: `src/scalim/dsl/yaml_dsl/runtime/**`
- CLI 辅助与一致性: `packages/scalim-cli/src/scalim_cli/yaml_dsl.py`
- docs: `docs/doc/yaml-dsl/**`(如涉及 `.gen.*` 或注入区块,只通过 `just gen-docs` 刷新)
- skills: `agentdev/skills/scalim-yaml-dsl/**`(如变更影响 authoring/校验入口)

## 3) “是否需要进 YAML”的判定提示

当某个字段/旋钮具有明显环境/运行入口差异时,默认应归类为 runtime policy:

- observability / diagnostics / staging
- retry / guardrails / performance knobs
- 与集成系统强绑定的策略

这类能力优先落到 Python/CLI entrypoints,而不是扩大 YAML authoring surface。

## 4) workflow 相关变更护栏

- workflow 的职责是 orchestration;不承担 fragment composition/imports expansion。
- 若出现 schema/runtime drift,优先修复契约(收紧 schema/runtime),而不是通过 workflow “补 imports” 兜底。

## 5) 验收口径(提交前必须过)

- 相关单测/回归测覆盖核心场景
- `just llmanspec-check`
- `just qa`
