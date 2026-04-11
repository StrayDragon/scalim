## Meta

- Type: `refactor-0`
- Topic: 重复校验规则的 SSOT 收敛（避免语义漂移：sheet 名校验、output 名正则等）
- Related code (重复实现示例):
  - Excel sheet name 校验：
    - `src/scalim/dsl/yaml_dsl/workflow_compile.py:123`（`_validate_excel_sheet_name`）
    - `src/scalim/dsl/yaml_dsl/runtime/output_composition_yaml.py:48`（`_validate_excel_sheet_name`）
  - output name 正则：
    - `src/scalim/dsl/yaml_dsl/runtime/compiler.py:101`（`_OUTPUT_NAME_PATTERN`）
    - `src/scalim/dsl/yaml_dsl/_internal/config_parsing/parsers/outputs.py:42`（`_OUTPUT_NAME_PATTERN`）

## 背景

YAML DSL 存在多条入口路径（workflow compile / runtime compile / internal parser），但它们面向的是同一套用户输入契约：

- `sheet_name` 的合法字符与长度约束（Excel 限制）；
- `outputs.*.name` 的命名规则；

当这些规则在多处重复实现时，长期必然出现：

- **语义漂移**：不同入口对同一输入的接受/拒绝不一致；
- **错误口径不一致**：用户在不同模式下得到不同提示，增加困惑与工单成本；
- **维护成本高**：修改规则要改多处，容易漏改；
- **测试难**：需要在多条入口上重复覆盖同一规则。

目前仓库已出现上述重复实现，并且两份实现的错误消息与细节已经不同（例如 “must be non-empty” vs “is required”）。

## 例子（漂移风险）

### 例子 1：sheet name 为空

- workflow compile 报错形态：`"{path} is required"`（`workflow_compile.py`）
- runtime output_composition_yaml 报错形态：`"Excel sheet name must be non-empty (path=...)"`（`output_composition_yaml.py`）

用户体验上：同一个错误，在不同入口提示不同；对排障与文档治理不利。

### 例子 2：invalid chars

两份实现都限制 `\\ / ? * [ ] :`，但一个逐字符检查，一个用集合交集后拼接，未来若调整字符集或提示格式，很容易只改到其中一个。

## 目标

- 将这类“输入契约规则”集中为 SSOT（Single Source of Truth）；
- 让所有入口调用同一实现；
- 错误消息与 path 口径统一为单一模板（包含 path/原因/修复建议）；
- 不改变规则本身（除非明确需要变更并在 proposal 标注）。

## 推荐方案

### 方案 A：新增 `dsl/yaml_dsl/_internal/validation_contracts.py`（推荐）

做法：

- 新增一个内部模块（示例）：
  - `src/scalim/dsl/yaml_dsl/_internal/validation_contracts.py`
- 定义并导出：
  - `EXCEL_SHEET_NAME_MAX_LEN`
  - `EXCEL_SHEET_NAME_INVALID_CHARS`
  - `validate_excel_sheet_name(name: str, *, path: str) -> None`
  - `OUTPUT_NAME_PATTERN` 或 `validate_output_name(name, *, path)`
- 将现有重复实现替换为 import 并调用。
- 同时将错误文案统一为单一模板（由 SSOT helper 生成），避免入口层再手写拼接导致漂移。

优点：

- 漂移源头被消除；
- 规则升级只改一处；
- 测试可以集中写一套，入口层只需薄测试确认接线正确。

缺点：

- 需要处理模块分层（workflow 与 runtime 都能安全 import `_internal`）；
- 需要决定错误消息格式是否统一（可能涉及少量回归更新）。

### 方案 B：只共享常量，不共享函数（不推荐）

缺点：

- 仍然会漂移（消息/边界处理不同）；
- 维护成本只降低一部分。

## 优劣分析与性价比

- 成本：低到中（改动集中在少数函数与常量，且对外行为基本不变）。
- 收益：高（消除长期漂移风险，提升一致性与可维护性）。
- 风险：低（若保持错误文案一致，风险更低；若统一文案，可能需要更新少量测试快照）。

## 验证建议

- 新增/迁移单测：
  - 覆盖 sheet name 的空值、超长、非法字符；
  - 覆盖 output name 的合法/非法（首字符、字符集、长度可选）。
- 在 workflow compile 与 runtime compile 各加一条薄集成测试，确认使用同一规则（例如断言报错码/关键信息一致）。
  - 建议额外断言错误文案遵循统一模板（含 `Hint:`），避免未来再次漂移。
