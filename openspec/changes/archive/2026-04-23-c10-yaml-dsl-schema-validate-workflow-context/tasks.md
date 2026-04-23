## 1. Core: workflow context + binding checks

- [x] 1.1 在 `src/scalim/dsl/yaml_dsl/validation_service.py` 增加 workflow resources id 提取（books + files），不展开 workflow imports
- [x] 1.2 在 `src/scalim/dsl/yaml_dsl/validation_service.py` 统一实现 outputs destination → resources 存在性校验（`to.book` ↔ `resources.books`，`to.file` ↔ `resources.files`），并修复 file outputs 被误报“Missing to.book”的假阳性
- [x] 1.3 将 workflow-level validate 的 demand 校验注入扩展为同时注入 `workflow.resources.books` 与 `workflow.resources.files`（保证 workflow validate 能捕获 unknown file id）

## 2. CLI: 参数与执行管线

- [x] 2.1 为 `packages/scalim-cli/src/scalim_cli/yaml_dsl.py` 的 `yaml-dsl schema validate` 增加 `--workflow <workflow.yaml>` 参数（仅对 demand entrypoint 生效）
- [x] 2.2 为 `packages/scalim-cli/src/scalim_cli/yaml_dsl.py` 的 `yaml-dsl validate`（demand 模式）增加 `--workflow <workflow.yaml>` 参数，并与 schema validate 复用同一套 core 上下文/绑定校验口径
- [x] 2.3 明确错误处理：workflow context 读取/解析失败时 fail-fast，并在 `--json` 输出中给出可定位错误 envelope

## 3. Tests: MVP 复现与回归

- [x] 3.1 增加最小复现 fixture：`workflow.resources.books/files` 声明 + demand 通过 `outputs[*].to.book/to.file` 引用；验证 `schema validate --workflow` 通过、无 `--workflow` 失败
- [x] 3.2 增加回归测试：有效的 `to.file` 输出在 schema validate/validate 中不应触发“Missing outputs to.book”假阳性
- [x] 3.3 增加错误用例测试：unknown book/file id 在提供 `--workflow` 后仍 fail-fast，且 path 指向 `outputs[0].to.book/to.file`
- [x] 3.4 增加错误用例测试：`--workflow` 指向不存在/不可解析文件时 fail-fast（schema validate + validate）

## 4. Docs / Skills（如需要）

- [x] 4.1 更新 CLI/skill 文档示例以包含 `--workflow`（SSOT 变更后运行 `just gen-docs`；禁止手工编辑任何 `*.gen.*` 或 AUTOGEN 注入块）

## 5. Quality gates

- [x] 5.1 运行 `just openspec-check`（sanitize + OpenSpec validate）
- [x] 5.2 运行 `just qa` 或至少覆盖新增测试用例的最小测试集
