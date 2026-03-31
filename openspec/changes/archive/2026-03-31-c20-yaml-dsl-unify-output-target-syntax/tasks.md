## 1. Schema DSL and config models

- [x] 1.1 为统一输出模型新增 `resources.files` / `file` 相关 schema_dsl dataclass、keys 与 enums,并移除 `outputs[*].container` 的用户侧 schema surface
- [x] 1.2 重构 `output_to` / `output_write` 数据模型: 支持 `to.file` 与通用 `write.include_header` / `write.header_fields_output_by`,并保留 books 专属 write 字段
- [x] 1.3 刷新 schema 生成物; SSOT=`src/scalim/dsl/by_yaml/schema_dsl/**`,生成入口=`uv run python scripts/gen-yaml-dsl-schema.py`,验收=`uv run python scripts/gen-yaml-dsl-schema.py --check`

## 2. Demand parsing and validation

- [x] 2.1 更新 demand loader/parser/validator: 解析 `resources.files`、`to.file`、统一 `write`,并对 legacy `container` 提供 fail-fast 迁移诊断
- [x] 2.2 统一“有效展示名唯一”触发条件,覆盖 file/books 两类输出与 `append`/`sheet` 差异
- [x] 2.3 更新 runtime overrides 解析: `overrides.outputs` 只接受统一 `to/write` surface,`overrides.resources` 支持 `resources.files`

## 3. Runtime and workflow compilation

- [x] 3.1 重构 output composition 编译链路,先归一化 output target,再分别推导 CSV / Excel `OutputSpec`
- [x] 3.2 引入 file resource 的路径/encoding 解析,并删除 runtime 对 `outputs[*].container` 的依赖分支
- [x] 3.3 更新 workflow compile / workflow validate: 支持 `workflow.resources.files` 与 `to.file`,并拒绝 legacy `container`

## 4. Migration diagnostics and tests

- [x] 4.1 为 YAML/overrides/workflow 三条入口补齐迁移错误信息: `container` 已移除、缺失 `to.file` / `to.book`、append 下禁止 `include_header`
- [x] 4.2 新增/更新单测与端到端测试,覆盖 file/books 统一 surface、真实 CSV/XLSX 头部行为、workflow validate 与 overrides 行为

## 5. Docs, examples, and generated artifacts

- [x] 5.1 更新文档与示例 SSOT,将 CSV authoring 全部改为 `resources.files + to.file + write`; 不手改 `.gen.*` 与 injected blocks
- [x] 5.2 刷新 docs 生成物; SSOT=`docs/doc/**/*.md` 与 schema SSOT,生成入口优先=`just gen-docs`,验收=`just qa` 中的 drift checks
- [x] 5.3 更新相关 skills / syntax references / OpenSpec 引用文本,确保不再把 `container` 当作当前 surface

## 6. Validation gates

- [x] 6.1 运行 `just openspec-check` 通过 OpenSpec sanitize + validate
- [x] 6.2 运行针对性 pytest,最终通过 `just qa`
