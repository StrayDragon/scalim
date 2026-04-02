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

在 design 阶段确定扩展工程放置位置（示例）：

- `frontend/vscode-extension/`（与其它前端资产同域）
- 或 `packages/scalim-yaml-dsl-vscode-extension/`（作为可发布包）

MVP 以“可本地运行与调试”为主，发布与签名后置。

2) **server provisioning：pinned 发行物 + venv**

- pinned 发行物默认建议：`scalim-yaml-dsl-lsp[server]`
- venv 存放于 `globalStorageUri`
- provisioning 失败时必须提示（并不影响用户继续用 YAML 基础编辑能力）

3) **schema 协作：不替换 redhat.vscode-yaml**

扩展通过配置 `yaml.schemas` 将：

- demand schema 绑定到 demand YAML（按 discovery 分类）
- workflow schema 绑定到 workflow YAML

## Risks / Trade-offs

- [目标机器缺少 Python 3.10+] → MVP 明确依赖；失败时给出可诊断提示与修复建议
- [不同工作区的 project discovery 不一致] → extension 以 workspace root 为单位管理实例，并输出 discovery 摘要

## Migration Plan

- MVP 先支持本地安装与开发；后续再考虑 marketplace 发布与自动更新策略。

## Open Questions

- pinned 版本来源：跟随仓库版本、还是由扩展配置项指定？
- server 启动命令：优先使用 console_script，还是 `python -m ...`？

