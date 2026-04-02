## 1. Serve 入口与基础骨架

- [ ] 1.1 在 `packages/scalim-yaml-dsl-lsp/` 增加 server 入口：`scalim-yaml-dsl-lsp serve`（默认 stdio；可选 tcp 仅 debug）
- [ ] 1.2 配置日志输出（stderr 或可配置文件），并确保初始化失败不输出半截 JSON-RPC
- [ ] 1.3 增加排障入口：`scalim-yaml-dsl-lsp dump-discovery <yaml_path> --json`（输出 discovery 摘要）
- [ ] 1.4 pygls 2.x 实现写法以 `pygls 2.1.x` docs/源码为准；仓库内参考 `.codex/skills/lsp-pygls-expert/references/`

## 2. 文档生命周期与 diagnostics

- [ ] 2.1 建立按 URI 的文本缓存（didOpen/didChange 更新）
- [ ] 2.2 didOpen/didChange 触发 diagnostics：复用 shared core，正确完成 1-based -> 0-based range 转换
- [ ] 2.3 异常降级：任何解析/计算异常返回空 diagnostics + 可诊断日志，不得崩溃/卡死

## 3. Python 引用跳转（definition）

- [ ] 3.1 接入 shared core 的 YAML 光标抽取（依赖 `yaml-dsl-lsp-yaml-cursor-extraction`），定位 `loader`/`call_by`/`retry.should_retry` 引用与 range
- [ ] 3.2 接入 shared core 的 Python definition 解析（静态、无副作用）；支持 `call_by(ref(args...))` 头部 `ref`
- [ ] 3.3 仅在光标位于引用 range 内触发；否则返回空结果

## 4. Hover 与 Completion（v1 最小可用）

- [ ] 4.1 hover：复用 shared core docstring 提取，失败降级为 warnings
- [ ] 4.2 completion：复用 shared core completion，失败降级为 warnings

## 5. 测试与回归门禁

- [ ] 5.1 对齐 `yaml-dsl-lsp-notebooks-regression`：将 notebooks fixtures 作为 gate（diagnostics + 引用解析不崩溃）
- [ ] 5.2 新增 LSP 层集成测试（启动、open/change、diagnostics、definition 的黄金路径）
- [ ] 5.3 运行 `just openspec-check` 确认 OpenSpec 工件结构与 schema 校验通过
