# yaml-dsl-editor-semantics-core Specification

## Purpose
定义可复用的 `YAML DSL` editor 语义 core（project discovery、diagnostics、Python 引用静态解析），作为 LSP server/工具链的 SSOT 实现。

## ADDED Requirements

### Requirement: Editor semantics core MUST expose project discovery
系统 MUST 提供 project discovery 能力，用于为 editor/LSP 侧推导：

- `project_root`
- `scalim_yaml_path`（可为空）
- `allowed_yaml_roots`
- `python_roots`

#### Scenario: nearest-wins scalim.yaml yields discovery payload
- **GIVEN** 某 `YAML` 文件位于项目子目录，且父目录链上存在 `scalim.yaml`
- **WHEN** editor 调用 project discovery
- **THEN** 返回的 `project_root` MUST 为最近的 `scalim.yaml` 所在目录
- **AND** 返回的 roots MUST 为绝对路径且可 JSON 序列化

### Requirement: Editor semantics core MUST expose diagnostics without invoking CLI
系统 MUST 提供 diagnostics API，且 MUST 直接复用 library 语义（schema/validator/unknown-fields），不得通过 shell-out 调用 CLI。

#### Scenario: diagnostics are computed without spawning a subprocess
- **WHEN** editor 请求某 YAML 的 diagnostics
- **THEN** 系统 MUST 返回结构化 diagnostics（errors/warnings + path + range）
- **AND** MUST NOT 依赖 CLI 子进程

### Requirement: Editor semantics core MUST be static and side-effect free
系统 MUST 保证 editor 语义为静态解析：

- MUST NOT 执行用户代码（仅允许文件系统读取与 AST 解析）
- MUST NOT 修改进程级全局状态（例如 `sys.path`、`sys.meta_path`）

#### Scenario: resolving definitions does not mutate process globals
- **GIVEN** editor 触发 go-to-definition
- **WHEN** core 解析某 Python 引用
- **THEN** 解析过程 MUST NOT 改写进程级全局搜索路径
- **AND** 解析失败时 MUST 返回空 locations + 可诊断 warnings

### Requirement: Python reference resolution MUST be filesystem + AST based
系统 MUST 支持对 Python 引用进行静态解析并定位定义位置：

- 引用格式 MUST 支持 `module:attr` 与 `module.attr`
- 定位 MUST 基于 `python_roots` + 文件系统模块解析 + AST 符号索引

#### Scenario: definition resolution locates a Python function
- **GIVEN** YAML 中某字段引用 `pkg.mod:func`
- **WHEN** 用户触发 go-to-definition
- **THEN** 系统 MUST 返回 `func` 定义所在文件与范围

