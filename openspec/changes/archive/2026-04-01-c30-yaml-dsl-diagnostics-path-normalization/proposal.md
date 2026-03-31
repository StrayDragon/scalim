## Why

当前 YAML DSL 的诊断链路需要同时满足:

- 语义校验产出的 `ValidationIssue.path` 可映射到 YAML 源码位置(`path:line[:column]`)
- CLI 输出与 JSON 输出具备稳定的路径口径,便于 IDE/CI/脚本消费

但现状存在两类一致性问题:

1) **path 语法不一致**: 一部分 validators 使用 `outputs[0].fields[1]` 的 bracket 风格,而 YAML location index 的 key 口径为 `outputs.0.fields.1`(点号 + 数字段). 结果是 CLI 经常无法为 issue 找到精确位置,退化到文件级或 root 级定位。

2) **重复校验路径漂移**: 某些规则在 validate 与 runtime compile 两处重复实现,一处产出结构化 issues,另一处抛出 `ValueError`,导致同一错误在不同入口表现不一致(类型/文案/路径)。

> 注意: 本 change 只处理**诊断/定位**使用的逻辑路径(例如 `ValidationIssue.path` / `ErrorEnvelope.path`)的语法一致性,不涉及 DSL 中 `extract` 等表达式的 dot+bracket 语法(例如 `extract: \"[1].x\"` 的 int-key 语义)。

## What Changes

- 定义并落地单一 canonical 逻辑路径口径:
  - **点号分段**(`a.b.c`)
  - **数组索引使用数字段**(`outputs.0.fields.1`),不使用 bracket 表达
- 在 CLI/定位层提供 path normalization,使 bracket 风格路径在不改动全部 validators 的前提下也能正确映射到 YAML 源码位置。
- 对关键重复校验点做“单点产出 issues”收敛(优先让 compile 复用 validate 的结构化诊断,或统一异常包装),避免同一错误在不同入口表现漂移。

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `yaml-dsl-cli-validation`: 统一 issue path 口径并确保 CLI 能稳定将逻辑路径映射到源码位置,同时收敛 validate/compile 的诊断形态差异。

## Impact

- CLI 输出: 错误定位将更精确,但部分错误的 path 文本可能发生变化(括号 -> 点号),需要更新回归测试断言。
- Validator/compile: 需要补充 path normalization 工具与少量热点规则的统一封装,降低重复实现导致的漂移。

## Sequencing

- 建议优先落地本 change,以便后续涉及校验收敛/文档修正的变更可以统一以 canonical dot path 为准编写回归断言。
