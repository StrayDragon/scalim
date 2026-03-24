## 1. Define and enforce the curated public surface

- [x] 1.1 盘点并固化稳定公开入口目录：`scalim.dsl.by_yaml`、`workflow` / `workflow_types` / `workflow_paths`、`scalim.spec.ir`，并明确哪些路径属于内部实现细节
- [x] 1.2 为稳定 facade 模块补齐或收紧显式导出白名单（`__all__` 或等价机制），避免内部符号无意泄漏
- [x] 1.3 补充 public-surface import smoke / export gate，使公开目录以白名单方式回归

## 2. Remove legacy sandbox from the default public API

- [x] 2.1 从 YAML DSL 官方公开入口的契约与实现中移除 `template_sandbox=legacy`，仅保留 safe sandbox
- [x] 2.2 对公共入口传入 legacy sandbox 的场景做 fail-fast，并提供明确迁移提示
- [x] 2.3 审查模板预编译相关调用链，确保默认公共 facade 不再暴露非显式 `unsafe` 的安全边界放宽能力

## 3. Move user-facing usage to the curated entrypoints

- [x] 3.1 将仓库内 tests / examples / skills 中的官方导入示例迁移到 curated public surface，不再推广内部实现路径
- [x] 3.2 扩展 marimo public API suite，使其覆盖 facade imports、workflow 辅助公开模块与 `scalim.spec.ir`
- [x] 3.3 增加内部路径漂移检查，防止 `runtime.*` / `config_parsing.*` / `schema_dsl.*` 重新出现在用户可见材料中

## 4. Sync specs and docs SSOT

- [x] 4.1 按本 change 的 delta specs 更新对应主规范（SSOT: `openspec/specs/**/spec.md`），并通过 `just openspec-check`
- [x] 4.2 若官方 docs 或注入内容引用了旧路径，更新手工 SSOT 并通过 `just gen-docs` 刷新生成物/注入区块，避免手改 `.gen.*` 或 `AUTOGEN` 区块

## 5. Acceptance

- [x] 5.1 运行面向 public surface 的 pytest / examples gate，确认 curated imports、legacy sandbox fail-fast 与内部路径漂移检查全部通过
- [x] 5.2 运行 `just qa`，确认 OpenSpec、测试与 docs drift gate 一致通过
