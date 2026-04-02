## Context

即便 YAML DSL LSP server 本身可运行，不同编辑器对 language server 的配置方式、workspace root 口径、以及日志/排障入口差异很大，导致用户经常遇到：

- “server 启动了但跳转不工作”（project discovery roots 不对）
- “imports 报 allowed roots 越界”（缺少 `scalim.yaml` 或配置不一致）
- “schema 与 LSP 互相打架”（误以为 LSP 负责 schema 校验）

需要把这些差异固化为一套可复制、可审计的文档。

## Goals / Non-Goals

**Goals:**

- 在 docs-site 中提供多编辑器接入指南（至少覆盖 Neovim / Zed / JetBrains）
- 明确 schema 与 LSP 的协作口径：
  - schema 插件（例如 VSCode 的 YAML 插件）负责结构校验/补全
  - LSP server 负责语义 diagnostics + Python 引用跳转/hover/补全 + actions
- 提供排障入口：
  - 如何查看 server 日志
  - 如何确认 project discovery 摘要（project_root/scalim_yaml_path/python_roots/allowed_yaml_roots）

**Non-Goals:**

- 不在本变更内实现编辑器插件（VSCode extension 在 `yaml-dsl-vscode-extension` 系列变更）
- 不替换或“接管” YAML schema 插件生态

## Decisions

1) **文档结构**

在 `docs/doc/yaml-dsl/` 下新增一个 LSP/IDE 集成目录（示例）：

- `docs/doc/yaml-dsl/lsp/index.md`
- `docs/doc/yaml-dsl/lsp/neovim.md`
- `docs/doc/yaml-dsl/lsp/zed.md`
- `docs/doc/yaml-dsl/lsp/jetbrains.md`
- `docs/doc/yaml-dsl/lsp/troubleshooting.md`

2) **配置片段可复制、可审计**

- 每个编辑器页提供最小可运行配置片段（启动命令、文件匹配、workspace root 说明）
- troubleshooting 页提供“最小排障 checklist”

3) **如需 injected blocks，必须明确 SSOT 与生成入口**

若需要在多个文档中复用相同命令片段（例如 server 启动命令），可考虑 injected blocks：

- SSOT 放在一个集中位置（例如 docs 配置片段文件）
- 生成入口统一走 `just gen-docs`

4) **排障口径：统一使用 dump discovery**

- 文档以 “dump discovery 摘要” 作为统一排障入口
- 推荐命令：
  - CLI：`scalim-yaml-dsl-lsp dump-discovery <yaml_path> --json`
  - LSP：`workspace/executeCommand` `scalim.dumpDiscovery`（若 client 支持/便于集成）

## Risks / Trade-offs

- [实现/文档漂移] → 优先使用可复用片段；必要时引入 injected blocks 并纳入 `just gen-docs`
- [不同编辑器支持差异导致文档失真] → 文档以“最低共同集”为主；高级功能（如 actions UI）交给 VSCode extension 文档补充

## Migration Plan

- 仅新增文档页，不改变运行时语义。

## Open Questions
（无；统一使用 dump discovery 作为排障入口）
