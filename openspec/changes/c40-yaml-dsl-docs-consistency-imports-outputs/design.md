## Context

该 change 的目标是“文档与提示一致性修复”,不涉及 DSL 语义变更。

约束:

- 文档治理: `*.gen.*` 与 `BEGIN/END AUTOGEN:*` 区块不可手改
- 仅修改 SSOT 文档页与源码中的用户提示文案,并通过既有生成/漂移门禁刷新与验收

## Goals / Non-Goals

**Goals:**

- docs 中关于 imports/$import 与 outputs.container 的表述与实现保持一致。
- validator 的迁移提示不得包含已无效语法示例(例如 workbook container),避免误导。
- capability matrix 对“支持/不支持”给出可执行口径(对应到 parser/validator 的真实边界)。
- skills 参考材料中出现的“已移除语法示例”(例如 `container.type: workbook` / `container.sheet`)必须被修正或明确标注为历史语法,避免持续误导。

**Non-Goals:**

- 不改变 schema/validator/parser 的接受集合与行为边界。
- 不在本 change 内做大规模文档重写;仅修正已确认漂移的段落与示例。
- 不承诺清理所有出现 “workbook” 字样的叙述(概念层面的 Excel workbook 仍存在);只清理“会让读者写出当前实现无法通过的 DSL 片段”。

## Decisions

1) **以实现为准更新文档**

- imports/$import: 以 `config_parsing/imports.py` + allowed roots 策略为准
- outputs.container: 明确仅 CSV; Excel 走 `resources.books` + `outputs.*.to`

2) **错误提示示例只提供当前可用写法**

- 迁移提示中的最小示例必须可通过当前 schema validate/validate(除非明确标记为“负例”)
- 保留负例 fixtures 作为 rejection tests,但不出现在用户文档

## Risks / Trade-offs

- [文档与实现再次漂移] 若后续实现继续演进,文档可能再次过期: 缓解:
  - 尽量引用 SSOT/spec 的稳定术语,减少描述实现细节
  - 通过 `just gen-docs` + `just qa` 的 drift gates 在 CI 中兜底

## Migration Plan

- (docs-only) 无用户迁移成本;用户按更新后的文档修正配置即可。

## Open Questions

- (none)
