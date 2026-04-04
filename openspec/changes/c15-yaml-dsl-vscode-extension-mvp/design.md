## Context

仅交付 LSP server 并不足以让 VSCode 用户开箱即用：

- Python 环境隔离与依赖安装需要扩展侧接管（避免污染用户全局环境）
- server 启动失败的排障需要统一入口（日志、版本、discovery 摘要）
- 与 `redhat.vscode-yaml` 的 schema 协作需要扩展侧明确配置口径

因此需要一个 VSCode extension MVP，作为大多数用户的默认入口。

## Goals / Non-Goals

**Goals:**

- 新增 VSCode extension MVP（可先本地安装/开发，不要求 marketplace 发布）：
  - 与 `redhat.vscode-yaml` 协作进行 schema 绑定（扩展不替换 YAML schema 插件）
  - 在 `globalStorageUri` 下维护隔离 venv，并以 pinned 版本安装/重装 LSP server 包
  - 以 stdio 方式启动 LSP server，并管理生命周期（启动/重启/崩溃提示）
  - 提供可诊断输出（日志、当前 server 版本、discovery 摘要）

**Non-Goals:**

- 丰富的 UX（状态栏细化、命令面板完善、actions 映射等）——后置到 `yaml-dsl-vscode-extension-actions-ux`
- 在扩展侧复制 YAML DSL 语义（语义必须来自 server/shared core）

## Decisions

1) **扩展工程位置与构建方式**

- MVP 工程固定在 `extras/vscode-scalim/`（已由 `yo code` 初始化：TypeScript + esbuild + pnpm）。
- 扩展源代码 **长期固定** 在 `extras/vscode-scalim/`（不迁移到 `packages/` 或 `frontend/`）。
- MVP 以“可本地运行与调试”为主；发布/签名/marketplace 后置，但不影响源码目录位置。

2) **server provisioning：pinned 发行物 + venv**

- pinned 发行物使用 `scalim-yaml-dsl-lsp[server]==<pinned_version>`（默认 pinned 为当前已验证版本；允许通过扩展配置覆盖）。
  - 当前建议默认值：`scalim-yaml-dsl-lsp[server]==0.7.5`（与仓库 `packages/scalim-yaml-dsl-lsp/pyproject.toml` 对齐）
- venv 存放于 `globalStorageUri`（单机复用；workspace 之间共享）
- provisioning 失败时必须提示（并不影响用户继续用 YAML 基础编辑能力）
- Python 解释器要求 >=3.10；当无法找到/版本不足时，必须输出可诊断提示（包含探测到的 python 路径与版本）

3) **schema 协作：不替换 redhat.vscode-yaml**

扩展通过配置工作区 `yaml.schemas` 与 `redhat.vscode-yaml` 协作（扩展不替换 YAML schema 插件）：

- schema 绝对路径从 pinned venv 内解析（避免与 server 版本漂移）：
  - `scalim-cli yaml-dsl schema path --type scalim_yaml`
  - `scalim-cli yaml-dsl schema path --type demand`
  - `scalim-cli yaml-dsl schema path --type workflow`
- MVP 先采用稳定、可解释的 glob 绑定（后续再增强为更贴近 discovery 的动态绑定）：
  - scalim.yaml schema → `scalim.yaml`
  - demand schema → `demand/**/*.y*ml`
  - workflow schema → `workflow/**/*.y*ml`
- 写入配置时必须 **idempotent merge**（保留用户已有 `yaml.schemas` 映射；只增补 scalim 相关项）

## Risks / Trade-offs

- [目标机器缺少 Python 3.10+] → MVP 明确依赖；失败时给出可诊断提示与修复建议
- [不同工作区的 project discovery 不一致] → extension 以 workspace root 为单位管理实例，并输出 discovery 摘要

## Migration Plan

- MVP 先支持本地安装与开发；后续再考虑 marketplace 发布与自动更新策略。
