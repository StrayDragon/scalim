## 1. Schema SSOT + 生成物

- [x] 1.1 在 `src/scalim/dsl/yaml_dsl/schema_dsl/models/` 为 source ref 字段新增 `default`（ordered cases）配置模型与 schema meta（包含 oneOf、`when` 枚举与 `call_by` 必须带 `()` 的约束）
- [x] 1.2 运行 `just gen-yaml-dsl-schema` 刷新 `src/scalim/dsl/yaml_dsl/schema/demand.gen.json`（禁止手改生成物），并确保 schema drift tests 通过

## 2. 严格校验与解析

- [x] 2.1 在 runtime strict validator 中实现校验：`default` 仅允许出现在带 `relation` 的字段上；unknown `when` / oneOf 违规 / `call_by` 缺失括号 必须 fail-fast
- [x] 2.2 复用现有 `call_by` 引用解析与 allowlist 机制：default 的 `call_by` 必须通过 allowlist（builtin `^...` 不要求 allowlist）
- [x] 2.3 实现 `default[*].call_by` 依赖校验：仅允许引用 pre-ref 可用字段（main_source 非 ref + 仅依赖这些字段的 derived）；依赖到 ref 字段/依赖 ref 的 derived MUST 在编译期 fail-fast，并给出可定位错误

## 3. IR/编译期表示

- [x] 3.1 为 ref 字段在 IR/ExecutionRequest 中携带 `default` cases（`when` + literal 或 call_by 解析结果），确保 planner/executor 可读取
- [x] 3.2 添加/注册 builtin callable `^defaults/zero_of_value_cast()`（与 `value_cast` 协同），并覆盖解析/执行路径

## 4. 执行期：LoadRef miss 写回默认值

- [x] 4.1 在 `LoadRef` 的 relation miss 写回路径应用 default cases（v1 仅 `relation_miss`，first-match；hit 行不受影响）
- [x] 4.2 确保默认值与命中值一致走 `value_cast` 转换路径；转换失败按既有 guardrails 行为处理
- [x] 4.3 保持性能：hit fast-path 零额外开销；literal default 为常量写回；仅在 miss 分支求值 `call_by`
- [x] 4.4 在 `when` 分支处理处添加 NOTE 注释，说明该 enum 设计用于未来扩展（v1 仅实现 `relation_miss`）

## 5. 观测与诊断

- [x] 5.1 增加按 field_id 聚合的 ref miss/default 命中统计（用于定位“数据缺失 vs 业务零值”），并在合适的日志/事件边界输出摘要

## 6. Editor/LSP

- [x] 6.1 在 `packages/scalim-yaml-dsl-lsp`/semantics core 的 diagnostics 中暴露 `default[*].call_by` 依赖违规的错误（与 runtime validator 一致）
- [x] 6.2 扩展 editor 语义抽取能力：将 `sources.*.fields.*.default[*].call_by` 视为 call_by 场景，支持 callable 头部引用的 hover/definition
- [x] 6.3 扩展参数段 token 抽取：在 `default[*].call_by(...)` 的 kwargs value 位置支持字段引用解析/补全（与 `fields.*.call_by` 一致）

## 7. 测试

- [x] 7.1 添加 YAML schema/strict validation 测试：合法 case、non-ref 拒绝、oneOf 拒绝、unknown when 拒绝、call_by 无括号拒绝、call_by 依赖 ref 字段拒绝
- [x] 7.2 添加执行期测试：relation miss 写回 literal/call_by；relation hit 不应用 default；default 仍经 value_cast

## 8. OpenSpec/QA

- [x] 8.1 运行 `just openspec-check` 与 `openspec validate --all --strict --no-interactive` 确保变更工件可归档
- [x] 8.2 运行 `just qa` 确保 lint/tests + drift gates 通过
