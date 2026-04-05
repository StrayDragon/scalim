## 1. OpenSpec / 验收门禁

- [x] 1.1 确认本变更仅修改手写文件（不编辑任何 `*.gen.*` 生成物 / injected blocks）
- [x] 1.2 运行 `just openspec-check` 校验 change artifacts 结构与 sanitize 规则

## 2. Editor semantics core（packages/scalim-yaml-dsl-lsp）

- [x] 2.1 在 core 内实现 `base_module_path` 推导：基于 `anchor_path.parent` + `python_roots`（静态、无副作用、deterministic）
- [x] 2.2 在 `resolve_python_definition()` 支持相对模块引用：`.mod` / `..mod` 规范化为绝对模块后再走现有模块定位 + AST
- [x] 2.3 扩展 `hover_python_reference()` / `complete_python_reference()` 以复用相同的相对模块规范化逻辑
- [x] 2.4 为无法推导 base / 越界 / 非法目录段 等失败形态补充可诊断 warnings 文案

## 3. LSP server 集成（packages/scalim-yaml-dsl-lsp）

- [x] 3.1 在 definition/hover/completion handler 中从 document URI 推导 `anchor_path` 并传入 core API
- [x] 3.2 确保 warnings 仍遵循“空结果 + 可诊断信息”的降级口径（不得 crash / 不得回显 YAML 正文）

## 4. 测试

- [x] 4.1 为 core 增加单测：`.loaders:fn` / `..loaders:fn` 的绝对化与定位（基于临时目录 + 假模块文件）
- [x] 4.2 为 core 增加单测：yaml 不在 `python_roots` 下时返回空结果 + warnings

## 5. 验证

- [x] 5.1 运行相关 pytest 子集（覆盖新增单测）
- [x] 5.2 在 VSCode 中打开含相对模块引用的 YAML，验证 definition/hover/completion 正常工作且无 warning
