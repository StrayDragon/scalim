## 1. Fixtures 发现与配置基线

- [x] 1.1 确认 notebooks fixtures 根目录与发现规则（排除 `.tmp/**`、`scalim.yaml`、`_shared/**`、`*_fragments.yaml`）
- [x] 1.2 在 fixtures 根目录新增最小 `scalim.yaml`，配置 `yaml_dsl.import_allowed_roots: ['.']` 以允许跨子目录 imports

## 2. Diagnostics 回归

- [x] 2.1 新增 pytest：遍历每个“完整 YAML”，调用 `scalim_yaml_dsl_lsp.core.collect_yaml_dsl_editor_diagnostics`
- [x] 2.2 断言：errors 为空；warnings 允许但输出结构必须可 JSON 序列化且 range（若存在）为合法区间

## 3. Python 引用回归

- [x] 3.1 从 YAML 文本抽取 `loader`/`call_by`/`retry.should_retry` 引用字符串（`call_by(ref(args...))` 仅回归 head `ref`）
- [x] 3.2 使用 pytest 显式注入 `python_roots`（例如 `src/`、`packages/scalim-misc/src`）并回归 definition/hover/completion 不崩溃

## 4. 验证与质量门禁

- [x] 4.1 将该回归纳入默认测试集合（避免仅在手工运行时生效）
- [x] 4.2 运行 `just openspec-check` 确认 OpenSpec 工件结构与 schema 校验通过
