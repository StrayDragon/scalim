## Context

当前仓库已存在稳定的 schema 生成治理链路：

- SSOT：`src/scalim/dsl/by_yaml/schema_dsl/**`（dataclass field metadata + constants/doc_texts）
- 生成入口：`scripts/gen-yaml-dsl-schema.py`（`just gen-yaml-dsl-schema`）
- 生成物：`src/scalim/dsl/by_yaml/schema/*.gen.json`（demand/workflow/scalim_yaml）
- 漂移门禁：`tests/governance/test_yaml_schema_generation.py` + `just schema-drift-check`

但字段级 `description/markdownDescription` 目前仍是“半结构化的自由文本”，存在覆盖不全、格式不统一、约束信息难以自动对齐的问题。我们需要把 schema 作为“用户 + agent”共同消费的权威描述面，把文档结构标准化并保证递归覆盖。

关键约束：
- 运行期零开销：变更仅影响 schema 生成与派生文档，不改变 runtime compile/validate/run 行为与性能边界
- SSOT 可维护：约束摘要应从 JSON Schema 自动推导，避免手写重复规则
- `$import` 语义需要被可读地表达（尤其 required 的 `anyOf` workaround）

## Goals / Non-Goals

**Goals:**
- 递归覆盖：对 demand/workflow/scalim_yaml 三份 schema 中的字段节点递归生成统一 `markdownDescription`
- 模板统一：所有配置项 hover 文档都以 `#### <配置路径>` 标题行开头，并按 doc level 使用 `brief/full` 模板（`full` 才包含约束与例子；枚举/复杂节点必须 `full`）
- 约束自动化：可选/必选/type/enum/default/pattern/min/max/oneOf 等由 schema 自动汇总
- 示例可复用：优先复用 schema `examples` 与从可运行 canonical YAML fixtures 提取的片段示例；缺失时提供最小合法示例骨架（保守策略）
- 生成期执行：标准化逻辑只在 `just gen-yaml-dsl-schema` 阶段运行（不进入 runtime 热路径）

**Non-Goals:**
- 不改变 YAML DSL 的运行期语义、校验规则或配置面
- 不新增/调整 YAML authoring surface 字段（本 change 聚焦文档结构）
- 不手工维护/编辑任何 `*.gen.*` 生成物或 injected blocks

## Decisions

### Decision 1: 在 schema 构建后做“统一文档标准化”后处理

在 `SchemaBuilder.build_*_schema()` 返回 schema dict 后，新增一个后处理阶段（doc standardizer）：
- 递归遍历 schema（`properties` / `definitions` / `items` / `oneOf|anyOf|allOf` 等）
- 对每个“配置项节点”（至少覆盖 `properties.*` 与 `definitions.*.properties.*`）生成：
  - `description`: 纯文本一行摘要（用于非 markdown 消费方）
  - `markdownDescription`: `brief/full` 两套模板之一
    - `brief`: 标题 + 短说明
    - `full`: 标题 + 说明 +（约束摘要 + 示例）

理由：
- 最小侵入：不要求把所有 workflow schema 重写为 dataclass；可对现有手写 dict 同样生效
- 覆盖稳定：统一遍历保证“递归覆盖”可被测试与 drift gate 约束

备选方案：在每个 dataclass field 手写完整模板（不可取：重复劳动 + 难以保证约束同步）。

### Decision 2: 语义文案仍以 schema_dsl meta 作为 SSOT，标准化层只做“包装 + 自动摘要”

约定：
- 标题行固定为 `#### <配置路径>`（自动推导，不包含摘要，避免歧义与人工维护漂移）
- “短说明/说明”优先取已有 `description`/`markdownDescription` 的首个非空行或正文（保持既有文案资产）
- 标准化层不试图重写语义解释；仅做模板包装，并在 `full` 节点上追加“字段约束/例子”

这样可以做到：
- 既保留现有 hover 文案（例如 loader 相对引用说明、迁移提示等）
- 又能在不手写的前提下补齐约束摘要与示例展示

### Decision 3: 标题使用自动生成的“上下文配置路径”，避免歧义与漂移

`markdownDescription` 的第一行标题将使用“配置路径”而不是仅使用字段名，以避免 `loader`/`kind` 等常见字段在不同上下文下产生歧义（例如 `main_source.loader` vs `source.loader`）。

约定：
- 配置路径 MUST 由生成器在遍历 schema 时自动推导（不得手写维护）
- 路径分隔符使用 `.`，数组 items 使用 `[*]`，mapping 动态 key 使用 `*`
- definition 内的路径以 definition 名称为根（例如 `definitions.main_source.properties.loader` → `main_source.loader`）

示例（仅示意）：
- `main_source.loader`
- `sources.*.key`
- `relations.*.steps[*].from`
- `workflow.runs[*].demand`
- `yaml_dsl.import_aliases`

### Decision 4: 约束摘要通过 schema 节点 + 上下文推导（含 `$import` required workaround）

标准化遍历需携带上下文信息：
- 父节点的 `required` 列表（用于推导当前 property 的 required/optional）
- 对 object schema 的 required workaround 做特判：
  - 识别 `anyOf: [ {required: <core>}, {required: ["$import"]} ]` 模式
  - 将其在摘要中表达为“满足 core required 集合 或仅 `$import`”

输出形式：在 `##### 字段约束` 下用 bullet list（稳定顺序）呈现。

### Decision 5: 示例渲染为 YAML code block，优先来自“可运行 fixtures 片段”

示例来源优先级（与规范一致）：
1) schema node 的 `examples`
2) 从可运行 canonical YAML fixtures 中提取的片段（通过 YAML comment 行 `# <!-- BEGIN/END AUTOGEN:<id> -->` 标记块提取；只提取局部片段，不内嵌完整 canonical example）
3) schema_dsl meta 中的示例元数据（若存在/补齐；尽量只保存 snippet id/引用，而不是手写大段 YAML）
4) 兜底：最小合法示例骨架（尽量浅、以通过 schema-only 校验为目标；不追求覆盖全部嵌套细节）

示例展示形式：YAML code block（而不是 JSON），便于直接复制到 authoring 文件。

实现上，示例渲染逻辑仅在生成阶段执行，可使用仓库内置的 YAML 能力（不引入新 runtime 依赖）。

## Risks / Trade-offs

- [schema 体积增大] → 通过约束摘要的“最小必要信息集 + 稳定顺序”控制长度；必要时为少数高频节点提供手工精简入口（仍由 SSOT meta 提供）
- [LSP hover 噪音/可读性] → 标题/约束/例子分段；保持一行摘要简短；长解释放在标题段落下方
- [递归覆盖的边界不清] → 在测试中明确“至少覆盖哪些节点”（properties/definitions.properties），并以断言保障
- [约束推导误差] → 约束摘要以“生成后的 schema”为准；若需要更准确的 required 语义（例如 `$import`），通过显式特判规则收敛

## Migration Plan

1) 实现 doc standardizer（仅生成期）并加入治理测试，确保递归覆盖与模板一致性
2) 运行 `just gen-yaml-dsl-schema` 刷新三份 `*.gen.json`
3) 运行 `just gen-docs` / `just gen-agent-skill` 刷新所有 schema 派生的受控生成物（避免 drift）
4) 通过 `just qa` / `just openspec-check` 验证门禁

回滚策略：
- 回滚 SSOT 代码变更并重新生成 schema（生成物由 drift gate 自动对齐）
