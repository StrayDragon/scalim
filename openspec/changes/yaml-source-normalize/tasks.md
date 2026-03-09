## 1. Source Normalize Surface

- [ ] 1.1 在 `schema_dsl` / parser / validator 中为 `sources.*` 增加 `normalize` 配置,并显式拒绝 `main_source.normalize`
- [ ] 1.2 为 `normalize.kind=index_by_key` 实现配置解析与校验,覆盖 `key_field` 必填和 `on_conflict=error|first|last` 规则
- [ ] 1.3 引入独立的 source-level normalizer 表示,避免直接复用现有 `LoaderIr.extractor`

## 2. Execution And Cache Integration

- [ ] 2.1 在 lookup source loader 调用后、`coerce_loader_result_mapping(...)` 前统一应用 `normalize`
- [ ] 2.2 更新 `preload_forever` 路径,确保 preload cache 写入的是 normalized mapping,并让 cache hit 与非缓存路径观察到同样结果形状
- [ ] 2.3 统一 instrumentation / diagnostics,确保对外看到的结果形状与实际执行/缓存使用的 normalized mapping 一致

## 3. Schema, Editor, Docs, Skill

- [ ] 3.1 更新 YAML schema 元数据: 为 `sources.*.normalize` 写入 source-level whole-result 语义、`index_by_key` 形状示例,并强调其先于字段 `extract`
- [ ] 3.2 重新生成 `src/scalim/dsl/by_yaml/schema/demand.gen.json`,并同步更新 `frontend/scalim-yaml-dsl-editor/src/schema/demand.gen.json`
- [ ] 3.3 更新 `docs/doc/` 下 YAML DSL 文档与示例,明确 `normalize` 与字段级 `extract` 的边界,并补充 `index_by_key` 示例
- [ ] 3.4 更新 `artifacts/skills/scalim-yaml-dsl/**`,确保 agent 能区分“whole-result reshape 用 `normalize`”与“字段嵌套取值用 `extract`”

## 4. Tests And Verification

- [ ] 4.1 新增测试覆盖: `index_by_key` 成功归一化、duplicate key 的 `error/first/last` 行为、缺失 `key_field` 的失败路径
- [ ] 4.2 新增测试覆盖: preload/cache 与非缓存路径都读取 normalized mapping,并验证字段级 `extract` 可基于 normalized row 正常工作
- [ ] 4.3 运行 `openspec validate --all --strict --no-interactive` 与相关 YAML/schema/editor drift 测试,确认工件和生成物一致
