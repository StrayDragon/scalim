## 1. 协议与命名

- [x] 1.1 定义稳定的 command id 列表与参数协议（供 VSCode/其它 client 复用）
- [x] 1.2 定义“explain-only”输出口径（无法安全编辑时仍可诊断）
- [x] 1.3 增加 debug command：`scalim.dumpDiscovery`（executeCommand，返回 JSON discovery 摘要）

## 2. Server handlers

- [x] 2.1 实现 `textDocument/codeAction`：基于 shared core diagnostics/discovery/warnings 决定 actions
- [x] 2.2 实现 `workspace/executeCommand`：将 command 映射为 `WorkspaceEdit`（或返回 explain-only）
- [x] 2.3 约束 edits 仅作用于 workspace 文件；越界时降级
- [x] 2.4 pygls 2.x handlers 写法以 `pygls 2.1.x` docs/源码为准；仓库内参考 `.codex/skills/lsp-pygls-expert/references/`

## 3. v1 Quick Fix 集合

- [x] 3.1 缺失 `scalim.yaml`：Create minimal `scalim.yaml`
- [x] 3.2 imports allowed roots 不包含需要目录：Add `yaml_dsl.import_allowed_roots`
- [x] 3.3 python_roots 缺失/不合理：Add `yaml_dsl.editor.python_roots`（推导为主，仅包含存在路径；无法安全修改则 explain-only）
- [x] 3.4 Python 引用不可解析：Explain resolution failure（不改写引用字符串）
- [x] 3.5 roots 类 Quick Fix 提供两档（最小修复 vs 更宽松），由用户选择 action 完成确认

## 4. 测试与验证

- [x] 4.1 添加 actions 回归测试：断言 WorkspaceEdit 内容与可撤销行为（至少覆盖 create scalim.yaml 与 add allowed roots）
- [x] 4.2 添加 executeCommand 回归：无效参数/异常路径不崩溃并返回可诊断信息
- [x] 4.3 运行 `just openspec-check` 确认 OpenSpec 工件结构与 schema 校验通过
