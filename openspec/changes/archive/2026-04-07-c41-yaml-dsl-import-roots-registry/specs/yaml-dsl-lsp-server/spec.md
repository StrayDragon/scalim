# yaml-dsl-lsp-server Specification

## MODIFIED Requirements

### Requirement: Go to Definition MUST support `$import` references statically
系统 MUST 为 demand YAML 中的 `$import` 引用提供 go-to-definition，且解析 MUST 为静态解析（不执行用户代码，不 shell-out CLI）：

- `$import` 引用格式 MUST 支持 `<alias>(.<segment>)*`
- 系统 MUST 基于当前文档顶层 `imports` 映射解析 `<alias>` 对应的 fragment 来源
- 系统 MUST 支持 `scalim.yaml` 中的 `import_roots` 重写 imports 路径解析（与 runtime imports 解析一致）
- 若 `$import` 引用可解析为 fragment YAML 文件与目标 mapping 位置，系统 MUST 返回该位置的 `Location`
- 解析失败 MUST 返回空结果且给出可诊断 warnings（不得 crash）

#### Scenario: go-to-definition jumps from `$import` to fragment mapping key
- **GIVEN** demand YAML 顶层声明 `imports: {fragments: ./ecommerce_report_fragments.yaml}`
- **AND** 某 mapping 内声明 `$import: fragments.report_book`
- **WHEN** 用户在 `$import` 引用字符串内触发 go-to-definition
- **THEN** 系统 MUST 跳转到 `ecommerce_report_fragments.yaml` 中 `report_book:` 对应的 key 位置

#### Scenario: unknown `$import` alias yields empty result
- **GIVEN** demand YAML 未声明 `imports.fragments`
- **WHEN** `$import: fragments.report_book`
- **THEN** go-to-definition MUST 返回空结果
- **AND** MUST 提供可诊断 warnings 提示 unknown alias

#### Scenario: fragment path escapes allowed roots yields empty result
- **GIVEN** `imports.fragments` 指向的 fragment 文件解析后越界（不在 allowed roots 内）
- **WHEN** 用户触发 go-to-definition
- **THEN** go-to-definition MUST 返回空结果
- **AND** MUST 提供可诊断 warnings 提示 path escapes allowed roots

