## 0. Public API Shrink (hard)

- [ ] 0.1 移除 `scalim.dsl.by_yaml.config_parsing.*` 旧导入路径: 将 `src/scalim/dsl/by_yaml/config_parsing` 迁移到 `src/scalim/dsl/by_yaml/_internal/config_parsing` 并新增 `src/scalim/dsl/by_yaml/_internal/__init__.py`
- [ ] 0.2 封堵内部导出面: `src/scalim/dsl/by_yaml/_internal/config_parsing/**` 下所有模块 `__all__` 必须为空(`[]`/`()`)以通过 public surface gate
- [ ] 0.3 全仓替换内部引用/测试导入路径: `scalim.dsl.by_yaml.config_parsing.*` -> `scalim.dsl.by_yaml._internal.config_parsing.*`
- [ ] 0.4 更新治理用例: `tests/governance/test_hotspot_*` 不再将 `config_parsing` 视为 public stable surface

## 1. Public Contracts (typed overrides)

- [ ] 1.1 在 `src/scalim/dsl/by_yaml/runtime/contracts.py` 定义 overrides dataclasses 与 `RunOverrides` 工厂方法(保持 Python 3.6 兼容;不新增模块)
- [ ] 1.2 更新 `src/scalim/dsl/by_yaml/__init__.py` 的 `__all__` 导出面,把新增类型纳入 Tier 1 稳定入口
- [ ] 1.3 为 legacy dict 输入添加 fail-fast 校验与迁移提示(错误信息指向 `RunOverrides.*` 逻辑路径)

## 2. Runtime Compiler Refactor (no dict parsing)

- [ ] 2.1 移除 `src/scalim/dsl/by_yaml/runtime/compiler.py` 中对 YAML-shaped overrides dict/list 的解析路径
- [ ] 2.2 将 typed overrides 映射为内部 schema dataclasses(例如 `OutputTargetConfig/ResourcesConfig/...`)并复用既有 outputs 编译流水线
- [ ] 2.3 保持并覆盖语义: overrides 优先级、fields 校验、to/container/write 互斥、overlay 语义与错误可定位性

## 3. Workflow Compile / Entrypoints Refactor

- [ ] 3.1 更新 `src/scalim/dsl/by_yaml/workflow_entrypoints.py` 传递 overrides 的方式(不再组装 mapping)
- [ ] 3.2 更新 `src/scalim/dsl/by_yaml/workflow_compile.py` 直接消费 typed overrides(不再解析 mapping/list/dict)
- [ ] 3.3 补齐 workflow 路径下的 overrides 回归: `resources/books` overlay、`outputs_defaults`、`outputs` 写节点生成一致性

## 4. Tests (accept typed / reject legacy)

- [ ] 4.1 升级 `tests/yaml_dsl/**` 中所有 `RunOverrides(outputs/resources/outputs_defaults=...)` 用例为 typed dataclasses
- [ ] 4.2 新增/补强用例: legacy dict 输入 fail-fast 且包含迁移提示
- [ ] 4.3 升级 `tests/workflow/**` 中的 overrides 用例(包含 workflow bundle viz 与资源覆盖场景)
- [ ] 4.4 运行并通过相关测试入口(验收口径): `pytest -q tests/yaml_dsl -q` + 相关 workflow tests

## 5. Docs / Examples (SSOT + drift)

说明:
- `docs/doc/**/*.md` 多数为手写 SSOT；任何包含 `.gen.` 的文件为生成物,禁止手改。
- 若涉及生成物/注入区块,以 `just gen-docs` 为唯一刷新入口(SSOT 在非 `.gen.` 文件或脚本中)。

- [ ] 5.1 升级 `docs/doc/yaml-dsl/user-guide.md` 中所有 overrides 示例为 typed dataclasses/工厂方法(移除 dict 旧写法)
- [ ] 5.2 升级其它用户材料中的 overrides 示例(例如 `docs/doc/viz/scalim-viz.md`,脚本/示例/notebooks 中的调用片段)
- [ ] 5.3 若 public API 文档为生成物,运行 `just gen-docs` 刷新并确保 drift gate 通过

## 6. OpenSpec / QA Gates

- [ ] 6.1 运行并通过 `just openspec-check`(sanitize + validate)
- [ ] 6.2 运行并通过 `just qa`(包含 lint/tests/drift)
