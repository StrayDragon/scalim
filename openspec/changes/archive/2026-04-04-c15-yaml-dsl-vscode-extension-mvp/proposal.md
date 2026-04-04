## Why

VSCode 是 YAML 编辑与 LSP 消费最常见的入口。仅交付 server 并不足以让多数用户“开箱即用”：Python 环境隔离、版本 pin、启动失败排障、以及与 `redhat.vscode-yaml` 的 schema 协作，都需要扩展层来管理。

因此需要一个 VSCode extension MVP，以最小功能集提供可用且可诊断的体验，并把 server 的启动与升级路径固化下来。

## What Changes

- 新增一个 VSCode extension MVP（不发布 marketplace 也可先支持本地安装/开发）：
  - MUST 与 `redhat.vscode-yaml` 协作进行 schema 绑定（扩展不替换 YAML schema 插件）
  - MUST 在 `globalStorageUri` 下维护隔离 venv，并以 pinned 版本安装/升级/回滚 LSP server 包
  - MUST 管理 LSP server lifecycle（启动/重启/崩溃提示），并提供可诊断输出（日志、当前使用的 python_roots 等）
- 扩展启动的 server 以 stdio 为主，遵循 `yaml-dsl-lsp-serve` contract。

非目标（本变更不做）：
- 丰富的 UX（状态栏、命令面板细化、actions 强化等，放在后续 `yaml-dsl-vscode-extension-actions-ux`）
- 在扩展侧复制/实现 YAML DSL 语义（语义必须来自 shared core + server）

## Capabilities

### New Capabilities

### Modified Capabilities
- `yaml-dsl-vscode-extension`: 明确并实现 VSCode extension v1 MVP 的 requirements（schema 协作 + venv provisioning + server lifecycle + 可诊断输出）。

## Impact

- 影响代码/资产：
  - `extras/vscode-scalim/` 下新增 VSCode extension 工程（扩展源代码长期固定在 `extras/`，不迁移到 `packages/`/`frontend/`）
  - `openspec/specs/yaml-dsl-vscode-extension/spec.md`：补齐 Purpose，并补充 MVP 范围与场景
- 依赖/运行时：
  - extension provisioning 需要目标机器具备 Python 3.10+（用于创建 venv 并安装 server 包）
