## Why

当前 `scalim.yaml` 的 imports 配置存在两类问题:

1) **配置冗余且容易误解**
- 典型项目会同时写 `yaml_dsl.import_aliases` 与 `yaml_dsl.import_allowed_roots`,并且经常指向同一批目录。
- 由于 imports 解析存在 “alias 重写” + “allowed roots 二次校验” 的组合,用户容易在 “我已经注册了 alias” 的前提下仍然因为缺少 allowed roots 而 fail-fast,造成心智负担与反复排障。

2) **多入口导致漂移与维护成本上升**
- `allowed_yaml_roots` 同时存在于: runtime 参数、CLI flags、以及 `scalim.yaml` 里,用户很容易维护两套口径(并产生 CLI/LSP/运行时不一致)。

我们希望把 imports 的“目录注册 + 路径重写 + 默认允许范围”统一到一个单一结构里,从源头消除重复与误解。

## What Changes

- 引入统一的 `yaml_dsl.import_roots` 结构,用一个列表同时表达:
  - imports 目录“注册”(作为可引用的 base dir)
  - 可选 alias(用于 `alias:/...` 或 `@/...` 前缀重写)
  - 默认 imports 允许读取的 roots(由注册目录集合推导,避免重复维护)
- **BREAKING**: 移除 `yaml_dsl.import_aliases` 与 `yaml_dsl.import_allowed_roots`。
- imports 展开与 LSP imports 解析逻辑改为只依赖 `yaml_dsl.import_roots`(不再要求用户在多个字段重复声明同一路径)。
- 保留调用侧的显式 `allowed_yaml_roots` 作为 override/收紧能力:
  - 当调用方显式提供 `allowed_yaml_roots` 时,其优先级高于 `scalim.yaml` 的默认推导(用于隔离/测试/最小权限场景)。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `yaml-dsl-project-config-schema`: `scalim.yaml` 项目配置 schema 改为 `yaml_dsl.import_roots` 单入口,并移除旧字段。
- `yaml-dsl-import-aliases-and-presets`: imports alias 重写与 roots 推导规则调整为基于 `import_roots`。
- `yaml-dsl-editor-project-discovery`: discovery 的 `allowed_yaml_roots` 推导与解释规则更新。
- `yaml-dsl-lsp-server` / `yaml-dsl-lsp-code-actions`: imports 诊断、code actions 与文档提示从旧字段迁移到 `import_roots`。
- `yaml-dsl-cli-validation`: CLI validate 默认行为与 project config 对齐(未显式指定 roots 时使用 `scalim.yaml` 的默认推导)。

## Impact

- 配置破坏性变更: 所有项目需从旧字段迁移到 `yaml_dsl.import_roots`。
- 影响代码范围:
  - `src/scalim/dsl/by_yaml/_internal/config_parsing/project_config.py`
  - `src/scalim/dsl/by_yaml/_internal/config_parsing/imports.py`
  - `packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/core.py` / server 侧 imports 相关逻辑
  - 生成物: `src/scalim/dsl/by_yaml/schema/scalim_yaml.gen.json` 与相关文档/技能 SSOT
- 影响用户体验:
  - imports 配置更短、更少重复。
  - CLI/LSP/运行时对 imports roots 的解释更一致,减少排障成本。

