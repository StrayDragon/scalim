## 1. vendors: yamlx import correctness

- [x] 1.1 修复 `src/scalim/vendor/yamlx/yaml/` 中对系统 `yaml` 的隐式依赖(避免 `cyaml.py` 误导入 `site-packages/yaml`)
- [x] 1.2 为 `src/scalim/vendor/yamlx/ruamel/yaml/` 增加导入期 bootstrap,确保内部 `ruamel.yaml.*` 绝对导入稳定指向 vendors 版本
- [x] 1.3 在可加载时将 `src/scalim/vendor/yamlx/_ruamel_yaml*.so` 作为可选 `_ruamel_yaml` 暴露(失败则自动回退 pure-python)

## 2. scalim: replace yaml imports with yamlx.yaml

- [x] 2.1 将 `src/scalim/cli/yaml_dsl.py` 的 `yaml` 引入替换为 `yamlx.yaml`
- [x] 2.2 将 `src/scalim/dsl/by_yaml/**` 内对 `yaml` 的可选依赖导入替换为 `yamlx.yaml`(包含 `yaml.nodes` 的类型/节点引用)

## 3. tests: lock in vendored behavior

- [x] 3.1 将 `tests/**` 中直接 `import yaml` 的用法替换为 vendors 入口,避免测试依赖外部安装包
- [x] 3.2 增加回归断言: `scalim.vendor.yamlx.yaml` 与 `scalim.vendor.yamlx.ruamel.yaml` 导入后,其 `__file__`/子模块解析不应来自 `site-packages`

## 4. py3.6 evaluation: ruamel.yaml vs PyYAML

- [x] 4.1 在 `/home/l8ng/Downloads/tmp/a/.venv`(Python 3.6.15) 下做最小对比实验(版本、功能差异、性能粗测)
- [x] 4.2 将对比结论写入变更文档(优先更新 `openspec/changes/c10-vendor-yamlx-and-switch-yaml-imports/design.md`)

## 5. verification

- [x] 5.1 运行 `just openspec-check` 校验 OpenSpec 工件
- [x] 5.2 运行与变更相关的最小测试集(例如 `pytest -q` 或子集)确保导入与 YAML DSL 校验通过
