## Why

当前 `PROJECT_CLI_NAME yaml-dsl upsert-lsp-comment` 固定写入 JetBrains/IntelliJ 兼容的 `# $schema: ...` 头,在部分编辑器/LSP(例如 Red Hat YAML Language Server)中不会生效,导致 schema 未被加载,从而影响 YAML DSL 的编辑体验与诊断质量。

同时,`PROJECT_CLI_NAME yaml-dsl schema-serve` 的引入成本与维护成本较高,且对实际工作流不是必须(可直接用本地文件路径/相对路径/HTTP URL 作为 schema 引用)。

## What Changes

- **BREAKING**: 移除 `PROJECT_CLI_NAME yaml-dsl schema-serve` 命令。
- 为 `PROJECT_CLI_NAME yaml-dsl upsert-lsp-comment` 增加 `--comment-style {all,jetbrains,redhat}`:
  - `all`: 同时 upsert JetBrains 与 Red Hat 两种 schema modeline
  - `jetbrains`: 仅 upsert `# $schema: <schema-ref>`
  - `redhat`: 仅 upsert `# yaml-language-server: $schema=<schema-ref>`
- 更新相关 OpenSpec 规范与回归测试,以反映上述行为变化与新的 CLI 参数。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `yaml-dsl-cli-validation`: 移除 `yaml-dsl schema-serve` 要求; 扩展 `upsert-lsp-comment` 支持多种 comment style。
- `yaml-dsl-agent-guidance`: 更新示例指令,不再依赖 `schema-serve`,并展示 `upsert-lsp-comment` 的新用法。

## Impact

- CLI: `PROJECT_CLI_NAME yaml-dsl schema-serve` 将不可用,需要从文档/脚本中移除或替换。
- Editor/LSP: `upsert-lsp-comment` 可生成 Red Hat YAML Language Server 识别的 modeline,也可保持 JetBrains 兼容。
- Code: 主要影响 `src/IMPL_ROOT/cli/yaml_dsl_lsp.py` 与相关测试文件。
- Specs: 需要同步更新 `openspec/specs/*/spec.md` 对应能力的 REQUIREMENTS(SSOT),变更内将以增量规范文件表达。
