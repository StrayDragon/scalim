## Context

现有 YAML DSL 的 loader params 模板支持 `{$runtime: <name>}` 指令节点,由调用方通过 Python 入口的 `runtime_vars` 注入值,并在 **编译期**解析为不透明 literal 透传给 loader。

问题在于命名: `runtime` 暗示“运行期动态求值/表达式”,但该能力本质是“初始化注入变量”(compile-time injection)。该误导会在:
- YAML authoring 与调试时造成错误预期(例如尝试字符串插值)
- workflow/IR 演进讨论时引入语义混乱(尤其当 workflow 引入 ctx/工件传递)

约束:
- runtime 需兼容 Python 3.6
- 文档/Schema 为强治理区域: `.gen.` 文件与 injected blocks 禁止手改,需走 `just gen-yaml-dsl-schema`/`just gen-docs`
- 用户明确要求不做兼容兜底: 一次性升级全仓写法

## Goals / Non-Goals

**Goals:**
- 将 `{$runtime: <name>}` 指令节点更名为 `{$init_var: <name>}`
- 将 Python 运行入口的 `runtime_vars` 更名为 `init_vars`,并同步 `RunOptions` 契约字段
- 同步更新 schema hover 文案/示例/错误提示,并更新 specs 与测试
- 明确 SSOT / generated / injected 边界与 drift gates,保证门禁可回归

**Non-Goals:**
- 不引入新的表达式/插值语法(仍禁止字符串子串插值)
- 不在本 change 内引入 workflow IR/节点系统或 dataset 工件传递(由 `c10-workflow-ir-roadmap` 拆分推进)
- 不保留旧写法兼容层(不提供 `$runtime` alias 或 `runtime_vars` 参数别名)

## Decisions

### 1) Breaking rename, no compatibility

选择: 直接删除 `$runtime`/`runtime_vars`,统一替换为 `$init_var`/`init_vars`。

原因:
- 避免双语法长期共存导致的文档/实现漂移
- 与仓库“新需求迭代不做兼容兜底”的约束一致

替代方案(不选):
- 保留 alias 并 deprecate: 需要额外的提示/统计/迁移窗口,且容易形成永久债务

### 2) Keep semantics: compile-time resolve + opaque literal

选择: 仅更名,保持语义不变:
- 解析发生在编译期(在 `DemandConfig -> DemandIr` 前完成)
- 注入值作为不透明 literal 透传(不得二次识别为 `$keys/$rows`)

原因:
- 该语义已在多处 spec 与实现中形成稳定契约(含 preload_forever/共享缓存签名校验)
- 更名不应改变行为边界,避免引入额外迁移风险

### 3) SSOT / Generated / Injected boundary and drift gates (MUST)

SSOT:
- 指令解析与错误信息: `src/scalim/dsl/by_yaml/params_template.py`
- schema hover 文案: `src/scalim/dsl/by_yaml/schema_dsl/constants.py`/`schema_dsl/**`

Generated(禁止手改):
- `src/scalim/dsl/by_yaml/schema/demand.gen.json`/`workflow.gen.json` (由 `scripts/gen-yaml-dsl-schema.py`)
- editor schema 镜像: `frontend/**/schema/*.gen.json` (由 `just gen-yaml-dsl-editor-schema`)
- docs 中的 `.gen.` 文件与 injected blocks (由 `just gen-docs`)

Drift gates:
- `just gen-yaml-dsl-schema` + `just gen-yaml-dsl-editor-schema` 生成并提交 schema
- `just gen-docs` 刷新 docs-site 与 injected blocks
- `just qa` 回归测试与 drift check
- `just openspec-check` 校验 OpenSpec 工件与 sanitize 规则

## Risks / Trade-offs

- [BREAKING 影响面大] → 一次性升级所有 YAML/文档/测试/示例;在错误提示中明确指向新写法 `{$init_var: ...}`
- [命名变更易遗漏角落] → 以 ripgrep 全仓搜索 `$runtime`/`runtime_vars` 并建立回归测试;包含 schema hover/升级指南/fixtures
- [workflow 相关签名预检依赖注入字典名] → 保持注入语义不变,仅改字段名与错误路径,并为 workflow 预检补齐覆盖

## Migration Plan

1) 先改核心 SSOT: params template directive、运行入口参数、RunOptions 契约与错误提示
2) 全仓升级:
   - YAML fixtures/examples/docs: `{$runtime: ...}` → `{$init_var: ...}`
   - Python 调用侧: `runtime_vars=` → `init_vars=`
3) 运行生成与门禁:
   - `just gen-yaml-dsl-schema`/`just gen-yaml-dsl-editor-schema`
   - `just gen-docs`
   - `just qa`/`just openspec-check`

## Open Questions

- spec 名称是否要从 `yaml-runtime-vars` 重命名为更贴近语义的名字?（建议暂不动,先完成指令/API 更名,避免扩大迁移面）
