## 1. SSOT 与生成边界收敛

- [x] 1.1 明确“配置项节点”的递归覆盖边界与遍历策略（至少覆盖 `properties.*` / `definitions.*.properties.*`，并决定是否覆盖 `items/oneOf/anyOf/allOf` 子节点）
- [x] 1.2 在 `src/scalim/dsl/by_yaml/schema_dsl/**` 内设计 doc standardizer 的 SSOT 结构（标题/摘要来源、约束摘要推导、examples 渲染策略），确保仅 gen 阶段执行

## 2. Doc standardizer 核心实现（gen-only）

- [x] 2.1 在 `src/scalim/dsl/by_yaml/schema_dsl/` 实现递归遍历与节点改写：统一生成 `description`（纯文本）与 `markdownDescription`（支持 `brief/full` 两套模板）
- [x] 2.2 实现“字段约束”摘要生成：required/optional/type/enum/default/pattern/min/max/items/additionalProperties 等稳定输出顺序
- [x] 2.3 实现 `$import` required workaround 的识别与摘要表达（`anyOf(required=core | required=$import)` → 二选一语义）
- [x] 2.4 实现标题“配置路径”的自动推导（definitions root、array items `[*]`、mapping key `*` 等规则），确保能区分 `main_source.loader` / `source.loader` 等常见字段
- [x] 2.5 实现 doc level 判定：基础容器节点优先 `brief`；枚举/复杂约束/outputs 聚合等节点强制 `full`
- [x] 2.6 对 enum 节点提供“取值语义”能力：`full` 模板的说明部分需列出每个枚举值并说明其行为/结果差异（并增加一致性检查/测试）

## 3. 示例渲染与缺口策略

- [x] 3.1 实现从 schema `examples` 渲染 YAML code block 的稳定输出（允许格式化差异但语义一致）
- [x] 3.2 设计并实现“最小合法示例骨架”兜底策略（保守：以通过 schema-only 校验为目标，不追求覆盖深层嵌套），并在输出中明确其为兜底最小示例
- [x] 3.3 定义 snippet block 规范（YAML comment 行 `# <!-- BEGIN/END AUTOGEN:<id> -->`），并选择 canonical YAML fixtures（优先 notebooks 中真实对拍 YAML）作为示例来源
- [x] 3.4 实现 snippet extractor（gen-only）：按 snippet id 从 fixtures 中提取 **局部片段** 并渲染为 YAML code block（避免手写片段漂移/不可运行）
- [x] 3.5 盘点高频字段缺少 examples/snippets 的位置：优先通过“为 fixtures 增加 snippet blocks + 为 schema_dsl 配置引用”补齐关键示例（避免在 schema_dsl 直接手写大段 YAML）

## 4. 接入三份 schema 生成管线

- [x] 4.1 将 doc standardizer 接入 `SchemaBuilder.build_demand_schema()`（输出 `demand.gen.json`）
- [x] 4.2 将 doc standardizer 接入 `SchemaBuilder.build_workflow_schema()`（输出 `workflow.gen.json`；保持 `$import` 不暴露的约束不变）
- [x] 4.3 将 doc standardizer 接入 `SchemaBuilder.build_scalim_yaml_schema()`（输出 `scalim_yaml.gen.json`；保持 `scalim.yaml` 可选性语义不变）

## 5. 治理测试与验收口径

- [x] 5.1 在 `tests/governance/` 增加断言：生成后的 schema 对应节点递归具备 `markdownDescription` 且符合模板（`####` + 两个 `#####` 小节）
- [x] 5.2 增加针对关键节点的语义守护测试（例如 `$import` workaround 摘要、required/optional 摘要、examples 渲染存在性）
- [x] 5.3 增加 snippets 治理测试：snippet id 必须可解析、提取结果非空、片段可被 YAML 解析（避免 fixtures 漂移导致示例失效）
- [x] 5.4 验证运行期零开销：确保 runtime 关键链路不引入 doc standardizer 依赖（以 import graph/测试用例约束）

## 6. 刷新生成物与下游派生（禁止手改生成物）

- [x] 6.1 刷新 schema 生成物：运行 `just gen-yaml-dsl-schema`（SSOT: `src/scalim/dsl/by_yaml/schema_dsl/**` → 生成物: `src/scalim/dsl/by_yaml/schema/*.gen.json`）
- [x] 6.2 刷新 docs 站点派生：运行 `just gen-docs`（受控生成物/注入区块，避免 drift）
- [x] 6.3 刷新 agent-skill 派生：运行 `just gen-agent-skill`（更新 `artifacts/skills/scalim-yaml-dsl/references/*.gen.*`）
- [x] 6.4 验收：运行 `just qa` + `just openspec-check`（确保 schema drift、docs drift、OpenSpec 校验均通过）
