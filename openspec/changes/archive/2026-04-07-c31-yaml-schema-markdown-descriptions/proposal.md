## Why

当前 YAML DSL / 项目配置(`scalim.yaml`)的 JSON Schema 已经具备“schema_dsl SSOT → `*.gen.json` 生成物 → drift gate”的治理链路，但字段级 `description/markdownDescription` 的风格、信息密度与覆盖深度仍不一致：

- 不能保证 **递归覆盖** 到 `definitions` 下的每一个 property（大量节点缺少统一的 hover 结构）
- “可选/必选/enum/default/oneOf 等约束”往往需要读 schema 或手写文案，难以长期对齐实现
- `$import` 的 schema-workaround(例如 required 的 `anyOf`)会让工具/文档很难稳定表达“实际必填边界”

我们即将大规模铺开 YAML authoring（用户 + agent），需要把“字段语义 + 约束 + 例子”收敛为可自动对齐维护的 SSOT，并以统一格式输出到 schema（从而在 IDE/LSP、docs、agent reference 中复用）。

## What Changes

- 为 YAML DSL / workflow / `scalim.yaml` 的 JSON Schema 生成管线新增“文档标准化”阶段：对 schema 节点做递归遍历，生成/改写每个节点的 `markdownDescription`（并保证 `description` 同步）。
- 强制统一 `markdownDescription` 模板（Markdown），每个配置项输出 `brief/full` 两套模板之一：
  - `brief`（基础/无争议）：
    - `#### <配置路径>`（配置路径需包含上下文；由生成器自动推导，避免人工维护导致漂移）
    - 短说明（1~3 行）
  - `full`（枚举/复杂/outputs 聚合等）：
    - `#### <配置路径>`
    - 说明（可多段；枚举需细化每个取值的行为与结果）
    - `##### 字段约束`：由 JSON Schema 自动生成（required/optional/type/enum/default/pattern/min/max/oneOf/anyOf/allOf/additionalProperties…）
    - `##### 例子`：优先复用 schema 的 `examples` 与从“可运行 canonical YAML”提取的片段示例（通过 YAML comment 行 `# <!-- BEGIN/END AUTOGEN:<id> -->` 标记块提取）；必要时才提供最小合法示例骨架（并明确缺口）
- 将“可选性/required 边界/$import 作用域与冲突 workaround”等关键规则收敛为可复用的生成逻辑（避免在各字段手写重复文案）。
- 保持运行期零开销：上述标准化逻辑仅在 `just gen-yaml-dsl-schema`（`scripts/gen-yaml-dsl-schema.py` → `schema_dsl/builder.py`）执行；不改变 YAML DSL runtime compile/validate 的执行路径与性能边界。
- 新增 snippets SSOT：从 `notebooks/` 等目录中的真实、可运行 YAML fixtures 中提取 **局部片段** 作为示例来源（schema hover 不内嵌完整 canonical example，避免长文与漂移）。

生成物与治理说明（SSOT → 生成物）：
- SSOT：`src/scalim/dsl/by_yaml/schema_dsl/**`（models/constants/doc_texts + builder 文档标准化逻辑）
- 生成物：`src/scalim/dsl/by_yaml/schema/*.gen.json`（由 `just gen-yaml-dsl-schema` 生成；禁止手改）
- 下游受控生成物会随之更新（来自 schema 的派生）：`docs/doc/yaml-dsl/schema-reference.gen.md`、`artifacts/skills/scalim-yaml-dsl/references/*.gen.*` 等（各自通过 `just gen-docs` / `just gen-agent-skill` 刷新）

## Capabilities

### New Capabilities
- （无）

### Modified Capabilities
- `yaml-dsl-schema`: 扩展 schema 生成器，使其对所有 schema 节点递归生成标准化 `markdownDescription`，并提供“约束摘要 + 示例”结构。
- `yaml-dsl-project-config-schema`: 同步将相同的标准化策略覆盖到 `scalim.yaml` 的 schema 节点（递归到 definitions/properties）。

## Impact

- 影响的代码/SSOT：
  - `src/scalim/dsl/by_yaml/schema_dsl/**`（新增/调整文档标准化生成逻辑与必要的 meta）
  - `scripts/gen-yaml-dsl-schema.py` / `just gen-yaml-dsl-schema`（作为唯一生成入口继续保持不变）
- 影响的生成物（由生成器刷新，不可手改）：
  - `src/scalim/dsl/by_yaml/schema/demand.gen.json`
  - `src/scalim/dsl/by_yaml/schema/workflow.gen.json`
  - `src/scalim/dsl/by_yaml/schema/scalim_yaml.gen.json`
- 影响的用户/agent 体验：
  - YAML LSP hover 将统一呈现“标题/约束/例子”，更易理解与迁移
  - docs/skill 的 schema 派生参考将更一致、更适合被 agent 消费
- 对 notebooks/fixtures 的要求：
  - canonical YAML 应尽量覆盖常见/关键的 YAML DSL 用法
  - 需要通过 YAML comment 行 `# <!-- BEGIN/END AUTOGEN:<id> -->` 标记块提供可复用的 **片段级** 示例（用于 schema `##### 例子` 自动对齐；保持 YAML 可运行）
- 运行期语义不变：不改变 YAML DSL 的编译/校验/执行行为，仅增强 schema 文档与编辑器提示能力
