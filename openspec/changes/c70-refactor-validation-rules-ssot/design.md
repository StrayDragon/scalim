## Context

YAML DSL 存在多条入口路径（workflow compile / runtime compile / internal parser / CLI validate），但它们面向的是同一套用户输入契约。例如：

- Excel `sheet_name` 的合法字符与长度约束；
- `outputs[*].name` 的命名规则（正则）。

当这些规则在多处重复实现时，长期必然出现语义漂移与错误口径不一致：

- 不同入口对同一输入接受/拒绝不一致；
- 错误消息与 path 表达不同，用户在不同命令/模式下得到不同提示；
- 修改规则需要改多处，容易漏改；
- 测试需要在多条入口上重复覆盖同一规则。

当前仓库已出现重复实现并开始漂移（例如 sheet name 空值的错误文案不同）。这属于典型 refactor-0：收敛 SSOT，避免未来扩散。

## Goals / Non-Goals

**Goals:**

- 将 “sheet name 校验 / output name 命名规则” 等输入契约集中为单一 SSOT 实现
- 所有入口复用同一实现，避免语义漂移
- 错误消息与 path 口径统一为单一模板（包含 path/原因/修复建议），便于 CLI/LSP 定位与文档治理
- 不改变规则本身（除非明确标注并配套迁移说明）

**Non-Goals:**

- 不在本次引入新的规则或更改 Excel/命名约束（仅做去重与一致性治理）
- 不把所有 validator 逻辑都一次性迁移（本次仅聚焦重复且高频的契约规则）

## Decisions

### 1) 新增内部 validation contracts 模块作为 SSOT（方案 A）

新增 `src/scalim/dsl/yaml_dsl/_internal/validation_contracts.py`（或等价位置）并导出：

- `EXCEL_SHEET_NAME_MAX_LEN`
- `EXCEL_SHEET_NAME_INVALID_CHARS`
- `validate_excel_sheet_name(name: str, *, path: str) -> None`
- `OUTPUT_NAME_PATTERN` 或 `validate_output_name(name: str, *, path: str) -> None`

并将现有重复实现替换为 import + 调用该 SSOT。

模块位置与依赖边界原则：

- workflow compile 与 runtime compile 都必须能安全 import（避免循环依赖）
- 该模块只包含纯校验/常量，不依赖重型运行时对象

### 2) 测试集中覆盖 SSOT，并为入口层保留薄接线测试

测试策略：

- 对 SSOT 校验函数集中写单测（空值、超长、非法字符；output name 合法/非法）
- 在 workflow compile 与 runtime compile（以及必要时 CLI validate）各加一条薄测试，确认它们确实调用 SSOT（例如断言关键错误信息与 path 一致）

### 3) 错误文案统一为单一模板（path/原因/修复建议）

为避免同一规则在不同入口出现“结论一致但文案漂移”，本变更将错误文案统一为单一模板：

- SSOT 校验函数 MUST 通过集中 helper 生成错误消息（而不是在各入口手写拼接）
- 消息 MUST 同时包含：
  - canonical dot path（用于定位）
  - 失败原因（why）
  - 可行动修复建议（hint）

建议模板（示例）：

- `"{path}: {reason}. Hint: {hint}"`

具体例子：

- 空 sheet name：`workflow.resources.books.report.sheet_name: Excel sheet name must be non-empty. Hint: provide a non-empty string (max_len=31; invalid chars: \\ / ? * [ ] :).`
- 非法 output name：`outputs.0.name: Invalid identifier 'foo-bar'. Hint: expected [a-zA-Z_][a-zA-Z0-9_]*.`

## Risks / Trade-offs

- **错误文案回归**：若借机统一文案，可能需要更新少量快照/断言；建议 Phase 0 优先保持既有文案或至少保持关键字段一致。
- **模块分层风险**：若放置位置不当可能引入 import 环；通过 `_internal` 纯函数模块可控规避。

## Migration Plan

- Phase 0：新增 SSOT 模块 + 替换重复实现 + 补齐集中单测 + 各入口薄测试
- 后续：将更多重复校验逐步迁移到该模块（保持 scope 可控）

## Open Questions

- 无。
