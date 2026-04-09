# yaml-dsl-lsp-notebooks-regression Specification

## Purpose
复用仓库 `notebooks` 下的 YAML DSL fixtures 作为 editor semantics core 的静态回归输入，
用于持续回归 diagnostics 与 Python 引用相关的 editor/LSP 操作，避免仅基于合成 YAML 导致的行为漂移。

## Requirements
### Requirement: Notebooks YAML fixtures MUST be used as a static regression suite for editor semantics core
系统 MUST 提供一套 pytest 回归，复用仓库 notebooks 下的 YAML DSL fixtures 作为静态输入，用于回归 editor semantics core 的关键行为。

回归套件 MUST 满足：

- MUST 自动发现 fixtures 根目录下的 `*.yaml/*.yml`
- MUST 排除 `.tmp/**`、`scalim.yaml`、`_shared/**` 与 `*_fragments.yaml`
- MUST 对每个被纳入回归的 YAML 运行 core diagnostics，且要求无 errors（warnings 允许）
- MUST 不执行用户代码、不得 shell-out CLI

#### Scenario: diagnostics are stable for all included fixtures
- **GIVEN** fixtures 根目录存在多份 demand/workflow YAML
- **WHEN** 运行 notebooks fixtures 回归套件
- **THEN** 每个被纳入回归的 YAML MUST 产生 0 条 error diagnostics
- **AND** 任意 YAML 产生的 diagnostics MUST 具备可用于编辑器 underline 的 range（若该条 issue 有定位信息）

### Requirement: Python reference operations MUST not crash for fixtures-derived references
系统 MUST 从 fixtures YAML 中抽取 `loader`/`call_by`/`retry.should_retry` 等 Python 引用，并对每个引用回归以下操作不得崩溃：

- go-to-definition（definition）
- hover
- completion

允许返回空结果，但 MUST 输出可诊断 warnings（如解析失败原因）。

#### Scenario: reference resolution degrades gracefully
- **GIVEN** fixtures YAML 中存在一个 `call_by: "pkg.mod:fn(arg=1)"` 引用
- **WHEN** 回归套件对该引用执行 definition/hover/completion
- **THEN** 测试 MUST 通过且进程不得崩溃
- **AND** 若无法解析，结果 MUST 为空并包含 warnings

### Requirement: Notebooks regression suite MUST cover aggregate field references
系统 MUST 从 notebooks fixtures 中抽取 `outputs[*].aggregate` 相关的字段引用点（包括 group_by/metric field refs/rank refs/score_by_rank），并对每个引用回归以下操作不得崩溃：

- completion（Ctrl+Space / 手动触发）
- definition
- hover

允许返回空结果，但 MUST 输出可诊断 warnings（如解析失败原因）。

#### Scenario: aggregate field operations degrade gracefully
- **GIVEN** fixtures YAML 中存在 `outputs[*].aggregate` 且包含至少一个 field-id 引用点
- **WHEN** 回归套件对该引用执行 completion/definition/hover
- **THEN** 测试 MUST 通过且进程不得崩溃

### Requirement: Notebooks regression suite MUST cover `call_by` kwargs value field intelligence
系统 MUST 在 notebooks fixtures 回归中，覆盖 `call_by: "pkg.mod:fn(x=a)"` / `call_by: "^<id>(x=a)"` / `outputs[*].aggregate.fields.*.call_by` 这类参数值引用字段的场景，并对每个被抽取到的 field-id token 回归以下操作不得崩溃：

- completion（Ctrl+Space / 手动触发）
- definition
- hover

允许返回空结果，但 MUST 输出可诊断 warnings（如解析失败原因）。

#### Scenario: call_by kwargs value operations degrade gracefully
- **GIVEN** fixtures YAML 中存在 `call_by` 且包含至少一个 kwargs 值 token
- **WHEN** 回归套件对该 token 执行 completion/definition/hover
- **THEN** 测试 MUST 通过且进程不得崩溃
