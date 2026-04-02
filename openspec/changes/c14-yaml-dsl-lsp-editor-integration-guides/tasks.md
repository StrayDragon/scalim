## 1. 文档结构与 SSOT

- [ ] 1.1 确定 docs 目录结构（`docs/doc/yaml-dsl/lsp/*`）与导航入口（index/侧栏）
- [ ] 1.2 若引入 injected blocks：明确 SSOT、生成入口（`just gen-docs`）与 drift gate 口径

## 2. 编辑器接入指南

- [ ] 2.1 Neovim：最小配置片段（启动命令、文件匹配、workspace root 说明）
- [ ] 2.2 Zed：language server 配置片段与 YAML 关联方式
- [ ] 2.3 JetBrains：LSP Support 插件配置与注意事项

## 3. Schema 与 LSP 协作口径

- [ ] 3.1 增补“schema vs LSP”职责说明（不替换 schema 插件；两者协作）
- [ ] 3.2 给出推荐组合（例如 YAML schema 插件 + scalim YAML DSL LSP server）

## 4. Troubleshooting

- [ ] 4.1 增补排障 checklist：日志位置、常见失败原因（allowed roots/python_roots/scalim.yaml 缺失）
- [ ] 4.2 明确如何获得 discovery 摘要（推荐 `scalim-yaml-dsl-lsp dump-discovery <yaml_path> --json`），便于 issue 报告

## 5. 验证

- [ ] 5.1 运行 `just gen-docs`（如有 injected blocks）并检查文档页面渲染
- [ ] 5.2 运行 `just openspec-check` 确认 OpenSpec 工件结构与 schema 校验通过
