## 1. Source Normalize Surface

- [x] 1.1 在 `schema_dsl` / parser / validator 中为 `sources.*` 增加 `normalize` 配置,并显式拒绝 `main_source.normalize`
- [x] 1.2 为 `normalize.kind=index_by_key` 实现配置解析与校验,覆盖 `key_field` 必填和 `on_conflict=error|first|last` 规则
- [x] 1.3 引入独立的源级归一化器表示,避免直接复用现有 `LoaderIr.extractor`

## 2. Execution And Cache Integration

- [x] 2.1 在 lookup source loader 调用后、`coerce_loader_result_mapping(...)` 前统一应用 `normalize`
- [x] 2.2 更新 `preload_forever` 路径,确保 preload cache 写入的是归一化后的映射,并让 cache hit 与非缓存路径观察到同样结果形状
- [x] 2.3 统一 instrumentation / diagnostics,确保对外看到的结果形状与实际执行/缓存使用的归一化后映射一致

## 3. Schema, Editor, Docs, Skill

- [x] 3.1 更新 YAML schema 元数据: 为 `sources.*.normalize` 写入源级整体结果语义、`index_by_key` 形状示例,并强调其先于字段 `extract`
- [x] 3.2 重新生成 `src/scalim/dsl/by_yaml/schema/demand.gen.json`,并同步更新 `frontend/scalim-yaml-dsl-editor/src/schema/demand.gen.json`
- [x] 3.3 更新 `docs/doc/` 下 YAML DSL 文档与示例,明确 `normalize` 与字段级 `extract` 的边界,并补充 `index_by_key` 示例
- [x] 3.4 更新 `artifacts/skills/scalim-yaml-dsl/**`,确保 agent 能区分“whole-result reshape 用 `normalize`”与“字段嵌套取值用 `extract`”
- [x] 3.5 升级 canonical example `notebooks/marimo/examples/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`: 至少引入一个 `normalize.kind=index_by_key` 的真实使用场景(例如把某个 lookup source 的 loader 改为返回 list 并用 normalize 归一化)

## 4. Tests And Verification

- [x] 4.1 新增测试覆盖: `index_by_key` 成功归一化、duplicate key 的 `error/first/last` 行为、缺失 `key_field` 的失败路径
- [x] 4.2 新增测试覆盖: preload/cache 与非缓存路径都读取 normalized mapping,并验证字段级 `extract` 可基于 normalized row 正常工作
- [x] 4.3 运行 `openspec validate --all --strict --no-interactive` 与相关 YAML/schema/editor drift 测试,确认工件和生成物一致
- [x] 4.4 下游适配盘点: 读取 `.tmp/known-outer-paths-using-this-package.txt` 并对其中关联代码做同步升级(不得在输出中引用其内容)
