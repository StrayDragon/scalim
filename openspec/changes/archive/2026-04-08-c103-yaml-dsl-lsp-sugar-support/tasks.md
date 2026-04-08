## 1. `^<id>` builtin callable：completion / hover / definition

- [ ] 1.1 completion：在 `^` 后补全 builtin ids + 摘要（保守词表），call_by 位置提供 snippet
- [ ] 1.2 hover：解释 builtin 含义与关键约束（仅静态展示）
- [ ] 1.3 definition：首选跳 Python 实现；备选跳 SSOT 文档；失败返回可诊断 trace

## 2. imports path alias prefix：completion / hover / definition / quick fix

- [ ] 2.1 completion：补全 alias prefixes（`@/`、`ALIAS:/`）与 alias base_dir 下 `.yaml/.yml` 路径
- [ ] 2.2 hover：展示 resolved path + allow-roots verdict + trace
- [ ] 2.3 definition：跳到 fragment 文件（文件级即可）
- [ ] 2.4 quick fix：alias 缺失/越界时引导修复 `scalim.yaml`（WorkspaceEdit；必须用户确认）

## 3. `scalim://...` preset：可打开/可跳转

- [ ] 3.1 hover：解释 preset id、来源与只读属性
- [ ] 3.2 definition：打开只读 virtual document（或降级到 SSOT 文件/文档）

## 4. Validation

- [ ] 4.1 fixtures：builtin/alias/preset 的 completion/hover/definition 覆盖
- [ ] 4.2 运行 `just qa` + LSP notebooks regression
- [ ] 4.3 运行 `just openspec-check`
