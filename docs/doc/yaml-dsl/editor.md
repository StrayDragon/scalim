# YAML DSL 编辑器

??? note "适用读者"
    - 写 YAML 配置并希望获得补全/校验的使用方
    - 需要启用更严格语义校验(exact, Pyodide)的开发者

`frontend/scalim-yaml-dsl-editor/` 是一个 **text-first** 的 YAML DSL 编辑器:默认纯前端运行(不依赖 Python),提供基于 canonical schema 的补全/hover/schema 校验,并可选启用精确语义校验(Pyodide)。

## 快速开始

```bash
cd frontend/scalim-yaml-dsl-editor
pnpm install
pnpm dev
```

默认端口:`5174`(strictPort).

## Schema 同步

编辑器内置使用 `src/scalim/dsl/by_yaml/schema/*.gen.json` 的前端拷贝版本:

```bash
just gen-yaml-dsl-editor-schema
```

会生成/同步:

- `frontend/scalim-yaml-dsl-editor/public/schema/demand.gen.json`
- `frontend/scalim-yaml-dsl-editor/public/schema/workflow.gen.json`

提示: 若要在编辑器中校验 workflow YAML,可在文件头使用:

```yaml
# yaml-language-server: $schema=../schema/workflow.gen.json
```

## 使用要点

- 顶栏:新建模板 / 载入示例 / 插入 `$schema` header / 导入/导出/复制
- `strict`:把未知字段等“潜在问题”提升为 error(便于导出前收敛质量)
- Outline:基于 YAML AST 的快速导航(支持 anchors/comments 的位置保留)
- Issues:统一展示 schema/unknown-fields/(optional)semantic issues,并支持点击跳转

## (可选)精确语义校验(exact, Pyodide)

编辑器默认使用 local semantic 校验规则(纯前端内置).如需对齐 `scalim-cli yaml-dsl validate` 的精确语义校验,可准备 Pyodide 所需的 wheel/资源并在编辑器顶栏启用。

最小准备链路:

```bash
just frontend-yaml-dsl-editor-exact-prepare
just frontend-yaml-dsl-editor-exact-check-assets
just frontend-yaml-dsl-editor-dev-exact
```

更多细节见 `frontend/scalim-yaml-dsl-editor/README.md`。
