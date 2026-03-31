## Context

CLI 校验输出依赖两条输入:

- `ValidationIssue.path`(逻辑路径)
- YAML location index(从 YAML AST 构建的 `path -> (line, col)` 映射)

两者当前对数组索引的表达不一致(括号 vs 数字段),导致定位失败。同时,部分语义规则在 validate 与 compile 各自实现,形成两套错误形态。

## Goals / Non-Goals

**Goals:**

- 定义并在代码层落地 canonical 逻辑路径口径(点号 + 数字段)。
- CLI 定位层能兼容旧 bracket 风格 path,并在输出中统一呈现 canonical path。
- 收敛关键重复校验点的诊断形态,优先产出结构化 issues(而不是散落的 `ValueError`)。

**Non-Goals:**

- 不修改 DSL 语义与接受的配置集合(仅诊断/定位改进)。
- 不触碰 `extract`/`call_by` 等 DSL 表达式自身的语法与语义(它们也可能出现 `[]`),本 change 只处理诊断路径(`ValidationIssue.path`)与 YAML location index 的匹配与展示口径。
- 不要求一次性重写所有 validators 的 path 写法;先通过 normalization 兜底,再逐步清理热点。

## Decisions

1) **Canonical path format**

- 以点号分段表示 mapping key: `sources.orders.loader`
- 以数字段表示序列索引: `outputs.0.fields.1`
- 避免 bracket: 不再将索引编码为 `outputs[0]`

2) **Normalization at the boundary**

- 在“逻辑 path -> YAML 源码位置”的查找入口处做 normalization:
  - 将 `foo[0].bar[12]` 归一化为 `foo.0.bar.12`
  - 保持其余段不变
- 可选地在构造 `ValidationIssue` 时也做 normalization,以保证所有下游(含 JSON 输出)口径一致。

3) **Deduplicate diagnostics shape**

- 对重复规则优先收敛为“单点产出 issues”:
  - validate: 继续产出 `ValidationIssue`
  - compile/runtime: 复用同一校验函数或对 `ValueError` 做统一包装,最终在 CLI/用户侧呈现同一类错误结构与路径口径

## Risks / Trade-offs

- [路径文本变化] bracket -> 点号可能导致测试/脚本断言漂移: 缓解:
  - CLI/JSON 输出统一改为 canonical dot path(不保留 legacy bracket 口径)
  - 更新回归测试以断言 canonical path
- [覆盖不全] normalization 仅处理索引 bracket,对更复杂的 path 语法不做承诺: 缓解:
  - 明确 canonical 口径,并逐步修正 validators 产出
- [语法歧义] `[]` 在 DSL 其他字段(例如 `extract`)也有语义: 缓解:
  - 仅对诊断路径做 normalization,不对用户表达式字符串做任何改写/解释。

## Migration Plan

- 先落地 normalization + CLI 回归测试,保证定位显著提升且不要求一次性改完 validators
- 分批修复 validators 的 bracket path 写法,使其原生产出 canonical path

## Open Questions

- (none)
