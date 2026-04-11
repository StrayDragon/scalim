## 1. 新增 validation contracts SSOT 模块（方案 A）

- [ ] 1.1 新增 `src/scalim/dsl/yaml_dsl/_internal/validation_contracts.py`：集中定义 `EXCEL_SHEET_NAME_*` 常量与 `validate_excel_sheet_name(...)`，以及 `OUTPUT_NAME_PATTERN`/`validate_output_name(...)`
- [ ] 1.2 保持模块纯粹：只做常量/纯校验，不引入重型依赖，避免 import 环
- [ ] 1.3 在 SSOT 模块内新增统一错误文案 helper（模板包含 path/原因/修复建议），所有校验失败 MUST 通过该 helper 生成消息（避免入口层再手写拼接）

## 2. 替换重复实现（消除漂移源）

- [ ] 2.1 将 `src/scalim/dsl/yaml_dsl/workflow_compile.py` 与 `src/scalim/dsl/yaml_dsl/runtime/output_composition_yaml.py` 的 `_validate_excel_sheet_name` 替换为调用 SSOT
- [ ] 2.2 将 `src/scalim/dsl/yaml_dsl/runtime/compiler.py` 与 `src/scalim/dsl/yaml_dsl/_internal/config_parsing/parsers/outputs.py` 的 `_OUTPUT_NAME_PATTERN` 重复定义替换为 SSOT
- [ ] 2.3 统一错误文案为单一模板（包含 path/原因/修复建议）；尽量不在 Phase 0 改动规则本身（仅治理文案与实现收敛）

## 3. 测试（单点规则覆盖 + 入口薄接线）

- [ ] 3.1 为 `validation_contracts.py` 增加集中单测：sheet name 空值/超长/非法字符；output name 合法/非法；并断言错误消息遵循统一模板（含 `Hint:`）
- [ ] 3.2 在 workflow compile 与 runtime compile 各加一条薄测试，确认其复用同一规则（必要时断言关键错误字段一致）

## 4. 规范同步与验收门禁

- [ ] 4.1 将本 change 的 delta 规范同步到 SSOT：更新 `openspec/specs/yaml-dsl-cli-validation/spec.md` 增加 “validation contracts MUST be SSOT across entrypoints” 的要求
- [ ] 4.2 运行 `just openspec-check` 校验 OpenSpec 工件
- [ ] 4.3 运行 `just quick-qa-only-py`（或 `just qa`）作为最终验收
