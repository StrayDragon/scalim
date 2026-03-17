## 1. Core Rename (SSOT)

- [ ] 1.1 在 `src/scalim/dsl/by_yaml/params_template.py` 将指令节点从 `{$runtime: <name>}` 更名为 `{$init_var: <name>}` 并更新错误信息/诊断路径
- [ ] 1.2 让 legacy `{$runtime: <name>}` 指令节点 fail-fast,错误中包含配置路径与迁移提示 `{$init_var: <name>}`(不做 alias/兼容兜底)
- [ ] 1.3 将 by_yaml Python 入口与契约从 `runtime_vars` 更名为 `init_vars`(包含 `run/compile/run_workflow` 与 `RunOptions`),并全仓更新调用侧

## 2. Runtime Wiring

- [ ] 2.1 更新 `src/scalim/dsl/by_yaml/runtime/**` 内部传递链路: `compiler.py`/`conversion.py`/`_internal/conversion_sources.py` 等统一使用 `init_vars`
- [ ] 2.2 更新 workflow 入口 `src/scalim/dsl/by_yaml/runtime/workflow_entrypoints.py` 及其预检/共享缓存签名逻辑,确保注入字典更名不改变“编译期解析 + 不透明 literal”语义

## 3. Schema (SSOT + Generated)

- [ ] 3.1 更新 schema hover SSOT 文案中对 `{$runtime: <name>}`/`runtime_vars` 的描述为 `{$init_var: <name>}`/`init_vars`(SSOT: `src/scalim/dsl/by_yaml/schema_dsl/constants.py` 及同目录 schema DSL)
- [ ] 3.2 运行 `just gen-yaml-dsl-schema` 并提交生成物(禁止手改 `*.gen.json`)
- [ ] 3.3 运行 `just gen-yaml-dsl-editor-schema` 并提交生成物(禁止手改 `*.gen.json`)

## 4. Docs / Demos / Fixtures

- [ ] 4.1 全仓升级 YAML 写法: `{$runtime: ...}` → `{$init_var: ...}`(优先覆盖 docs/fixtures/demo YAML)
- [ ] 4.2 全仓升级 Python 调用: `runtime_vars=` → `init_vars=`(scripts/notebooks/tests)
- [ ] 4.3 运行 `just gen-docs` 刷新 `.gen.` 与 injected blocks(禁止手改生成物/注入块内部)

## 5. Tests & Gates

- [ ] 5.1 更新/新增测试覆盖:
  - `{$init_var: ...}` 编译期解析(main_source + sources)
  - 缺失 init var 的 fail-fast(含配置路径)
  - legacy `{$runtime: ...}` 明确报错与迁移提示
- [ ] 5.2 回归门禁:
  - `just qa`
  - `just openspec-check`
