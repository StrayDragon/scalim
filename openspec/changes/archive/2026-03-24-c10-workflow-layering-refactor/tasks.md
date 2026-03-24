## 1. Scaffold workflow framework layer

- [x] 1.1 新增 `src/scalim/workflow/` 包骨架（`__init__.py` 最小化 + 明确子模块职责）
- [x] 1.2 将 workflow 执行编排从 `src/scalim/dsl/by_yaml/runtime/workflow_execute.py` 迁移到 `src/scalim/workflow/**`（移除对 `scalim.dsl.*` 的静态依赖）
- [x] 1.3 迁移/收敛 workflow runtime 的核心协作单元：ctx/artifacts、resource manager、loader context、结果/错误模型、workflow-level events

## 2. Add YAML workflow adapter entrypoint (stable path)

- [x] 2.1 新增 `src/scalim/dsl/by_yaml/workflow_entrypoints.py`（稳定入口）并保留 per-call 注入 seam（至少 `run_ir_fn` + demand 编译回调）
- [x] 2.2 将 workflow 的“加载/编译”逻辑从 runtime 迁移到 `src/scalim/dsl/by_yaml/`（例如 `workflow_load.py`/`workflow_compile.py`），保持 `WorkflowIr` 编译与静态校验行为一致
- [x] 2.3 适配层以 callbacks 调用 `scalim.workflow` 的统一执行入口（确保 pathless CSV + workflow-managed temp outputs 仍可用）

## 3. Remove legacy runtime workflow modules (breaking upgrade)

- [x] 3.1 删除 `src/scalim/dsl/by_yaml/runtime/workflow_*.py`（不做兼容 shim），并修复仓库内所有引用
- [x] 3.2 全量升级内置 loader 引用路径到 `scalim.workflow.loaders:*`（含 YAML fixtures 与 allowlist）

## 4. Update tests & fixtures

- [x] 4.1 更新 workflow pytest 用例：入口导入从 `scalim.dsl.by_yaml.runtime.workflow_entrypoints` 改为 `scalim.dsl.by_yaml.workflow_entrypoints`
- [x] 4.2 更新 sheetbook loader 的引用与 allowlist：从 runtime 路径改为 `scalim.workflow.loaders`
- [x] 4.3 保持行为护栏：结果顺序、失败策略、事件归因、资源清理语义不漂移（以现有 workflow 测试套件为准）

## 5. Add QA gates for layering SSOT

- [x] 5.1 新增 pytest AST 扫描门禁：`src/scalim/workflow/**` MUST NOT import `scalim.dsl/**`
- [x] 5.2 新增 pytest 结构门禁：`src/scalim/dsl/by_yaml/runtime/**` 不得再包含 workflow runtime 模块/执行编排逻辑
- [x] 5.3 更新 `py36-typingext-check` 的 workflow import smoke test（至少覆盖 `scalim.dsl.by_yaml.workflow_entrypoints`），并通过 `just py36-typingext-check`

## 6. Specs & docs SSOT sync

- [x] 6.1 同步更新 OpenSpec 主规范（SSOT: `openspec/specs/**/spec.md`）以匹配本 change 的 delta specs，并通过 `just openspec-check`
- [x] 6.2 更新架构说明（SSOT: `ARCH.md`，并保持 `docs/doc/architecture/arch.md` 一致），并通过 `just doc-governance-check`

## 7. Acceptance

- [x] 7.1 运行 `just quick-check-only-py`（或 `just qa`）确保所有门禁通过
