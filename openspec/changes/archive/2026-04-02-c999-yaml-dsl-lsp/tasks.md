## 1. Review Gate (Maintainer)

- [x] 1.1 维护者确认本 change 不引入通用 YAML server,仅提供 editor semantic sidecar 边界（不替换 redhat.vscode-yaml）
- [x] 1.2 维护者确认 project discovery SSOT：复用 `scalim.yaml`（nearest-wins）+ 零配置兜底

## 2. Project Discovery & Config Surface

- [x] 2.1 定义 `yaml-dsl-editor-project-discovery` 的配置 schema（`scalim.yaml: yaml_dsl.editor` 或等价）并补齐解析/校验
- [x] 2.2 实现零配置 discovery：从入口 YAML 向上查找最近 `scalim.yaml`；未找到时以入口目录为 project root
- [x] 2.3 定义并实现 demand/workflow 分类策略（config override + 默认启发式），并写回归测试

## 3. Diagnostics API (Library, no CLI)

- [x] 3.1 抽出/新增 `scalim.dsl.by_yaml.editor_semantics`(或等价) 对外 API：输入 YAML path/text，输出结构化 diagnostics（含 range）
- [x] 3.2 demand diagnostics 复用现有 validator + YAML location index；确保路径口径与 CLI 一致（点号 + 数字段）
- [x] 3.3 workflow diagnostics v1 仅做 schema-only 校验；缺失 `jsonschema` 时输出 warning 并可继续（不得 crash）
- [x] 3.4 为 diagnostics 输出定义稳定的 JSON-serializable 数据结构（供 pygls/VSCode 消费），并补测试

## 4. Go-to-Definition / Completion / Hover (Static)

- [x] 4.1 定义 `loader`/`call_by` 等引用字段的 Python 引用格式与解析规则（`module:attr` / `module.attr`）
- [x] 4.2 基于 `python_roots` + `importlib.util.find_spec` 定位模块文件，并用 `ast` 找到 symbol 定义范围（不执行用户代码）
- [x] 4.3 提供最小 completion/hover：在引用字符串内补全可用 symbol，并展示 docstring/说明（失败降级为无结果）

## 5. Packaging / Resources / Docs

- [x] 5.1 确认 schema 资源可被外部读取（`src/scalim/dsl/by_yaml/schema/*.gen.json` 打包可用）；schema SSOT 为 `src/scalim/dsl/by_yaml/schema_dsl/**`
- [x] 5.2 若新增/修改 schema DSL，使用 `just gen-yaml-dsl-schema`(或 `just gen`) 刷新 `.gen.json`，并以 `just qa` 的 drift gate 验收
- [x] 5.3 增加 docs：LSP/VSCode 集成指南与 project discovery 说明；若涉及 injected blocks，SSOT 在 `docs/doc/**`，用 `just gen-docs` 刷新并通过 drift gate

## 6. Quality Gates

- [x] 6.1 运行 `just openspec-check` 确保 OpenSpec 工件一致性
- [x] 6.2 运行 `just qa` 通过 lint/tests + drift checks
