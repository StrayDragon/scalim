## Why

当前 YAML DSL 能表达的能力很强(多 source 关联、多级 relation、派生字段、params 模板、cache/normalize、输出与可观测性),但随着迭代积累,语法与约束已经变得“对新用户不直觉、对老用户也容易踩坑”:

- 同一类概念分散在多个位置(`main_source` vs `sources` vs 顶层 `fields` vs `output.fields`),理解成本高
- 关键路径依赖 YAML anchors/alias 的“对象身份”(例如 `output.fields`),对普通 YAML 用户非常反直觉
- relation 引用不支持字符串 ref(只能 alias 或内联 steps),可读性与可写性差
- `params` 同时包含 `$runtime.*` 占位符与 `$keys/$rows` 指令节点,对“模板 vs 运行期渲染”的心智负担高
- schema 与语义 validator 的双层约束 + 大量场景化报错,使得文档/skill 维护成本偏高

需要一次“大胆且一步到位”的语法重构,把 YAML DSL 校准到更直觉、更统一、可长期演进且对 editor/agent 更友好的形态。

## What Changes

- **BREAKING**: 设计并落地一套新的 canonical YAML DSL 语法(不引入 v1/v2/v3 版本预设;仓内所有示例/fixtures/skills/frontend 一次性迁移到最新语义)。
- 提出不少于 5 套候选语法方案(含若干微调方案),每套方案提供:
  - 语法目标与核心设计
  - 与现有能力的映射与可行性说明
  - 一个可读的 MVP 完整示例 YAML
- 本 change 只做提案与对比,不写任何实际代码逻辑;实现会在 review 选定方案后以独立 change 推进。

候选方案与预写材料落在:
- `openspec/changes/yaml-dsl-syntax-overhaul/mvp/plan-a/`
- `openspec/changes/yaml-dsl-syntax-overhaul/mvp/plan-b/`
- `openspec/changes/yaml-dsl-syntax-overhaul/mvp/plan-c/`
- `openspec/changes/yaml-dsl-syntax-overhaul/mvp/plan-d/`
- `openspec/changes/yaml-dsl-syntax-overhaul/mvp/plan-e/`
- `openspec/changes/yaml-dsl-syntax-overhaul/mvp/plan-f/`

## Capabilities

### New Capabilities
- `yaml-dsl-syntax-rewrite`: 定义“直觉化、统一化、一步到位迁移”的 YAML DSL 新语法的需求边界、评估标准与候选方案集(并产出可 review 的 MVP 示例)。

### Modified Capabilities
- （本 change 不直接修改现有规范要求;选定方案并进入实现时,将以单独 change 修改 `yaml-dsl-schema` / `demand-dsl` / `yaml-dsl-cli-validation` / `yaml-dsl-editor-core` / `yaml-dsl-agent-guidance` 等能力的 requirements。）

## Impact

- 语法与语义链路将受影响(后续实现阶段):
  - schema 生成: `src/scalim/dsl/by_yaml/schema_dsl/**` + `scripts/gen-yaml-dsl-schema.py`
  - 语义 validator: `src/scalim/dsl/by_yaml/config_parsing/**`
  - YAML → IR 转换与运行入口: `src/scalim/dsl/by_yaml/runtime/**`
  - CLI/LSP 与 editor schema: `src/scalim/cli/yaml_dsl.py` + `frontend/scalim-yaml-dsl-editor/**`
  - 文档/技能与 canonical demo: `docs/doc/yaml-dsl/**` + `artifacts/skills/scalim-yaml-dsl/**` + `notebooks/marimo/examples/**`

