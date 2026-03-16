## 1. YAML Schema / Model

- [x] 1.1 保持 `outputs[*].where` 字段名不变,更新 schema hover 文案(强调行级过滤谓词,非 sheet enable)
- [x] 1.2 将 `OutputAggregateConfig.metrics` 重命名为 `fields` 并移除旧字段(破坏性升级,不做兼容别名)
- [x] 1.3 为 `aggregate.fields.<field_id>` 增加“函数当 key”的 oneOf schema: 聚合函数 keys + rank keys + `call_by` hotfix key
- [x] 1.4 细化 schema hover/markdownDescription(尽可能详细,说明“控制什么/来自什么/何时执行/常见误用”):
  - `outputs[*].where`(行级过滤: 阶段/变量来源/聚合前限制)
  - `outputs[*].aggregate.group_by`(来源为 where 过滤后的行流;每组产 1 行)
  - `outputs[*].aggregate.fields`(producer key + 执行顺序 + 可引用字段范围)
  - 各 producer key(聚合函数/排名函数/call_by)的语义与参数说明
- [x] 1.5 运行并通过 schema drift gate: `tests/test_yaml_schema_generation.py`

## 2. YAML Parser / Validator

- [x] 2.1 更新 `src/scalim/dsl/by_yaml/config_parsing/parsers/outputs.py` 解析 `aggregate.fields`(并保持 `where` 逻辑不变)
- [x] 2.2 实现 `aggregate.fields` 的互斥校验: 每个字段必须且只能匹配一个 producer key(聚合函数 / rank / call_by)
- [x] 2.3 实现 rank 字段语义校验: `by` 引用合法、`partition_by ⊆ group_by`、`top_k_mode=rows` 必须提供 `order_by`

## 3. YAML Runtime Compile

- [x] 3.1 更新 `src/scalim/dsl/by_yaml/runtime/output_composition_yaml.py`:
  - 编译 `where` 为 predicate(row)->bool(保持语义不变)
  - 将 `aggregate.fields` 编译为 `DerivedGroupBySpec`(含 rank/score 等新增字段规划)
- [x] 3.2 更新 derived output 的导出 layout 生成逻辑: `group_by + agg fields + rank/score fields` 顺序确定且可对拍

## 4. Execution: derived outputs ranking & post fields

- [x] 4.1 扩展 `src/scalim/execution/derived_outputs.py::RankedGroupByAggregator` 支持:
  - `row_number`/`rank`/`dense_rank`
  - `partition_by`
  - `order_by` 多 key
  - `top_k_mode=rank|rows`(默认 rank 含并列扩张)
- [x] 4.2 在 finalize 阶段支持聚合后派生字段:
  - 内置 `score_by_rank`(优先,强补全)
  - `call_by` hotfix(弱补全,但受 allowlist 约束)
- [x] 4.3 明确并实现确定性规则: tie-break、排序稳定性与 top_k 截断策略(对拍友好)

## 5. Tests

- [x] 5.1 增加/更新 `tests/test_derived_outputs.py` 覆盖 dense/partition/top_k_mode 的核心边界
- [x] 5.2 增加 YAML parser/runtime 端到端测试: 用脱敏输入断言输出(替代 workflow+CSV workaround)
- [x] 5.3 覆盖 `where`(行级)在 detail 与 aggregate output 的行为一致性
- [x] 5.4 增加 schema 文案断言测试: 生成 schema 并校验关键节点 markdownDescription 包含“阶段/来源/顺序”等关键信息(防止 hover 回退为字段名描述)

## 6. Docs & Migration

- [x] 6.1 更新 YAML DSL 用户文档与 schema reference(通过 SSOT + `just gen-docs`,不手改 `.gen.`)
- [x] 6.2 提供迁移指引(机械替换规则 + 常见报错示例);必要时提供脚本化升级入口(不承诺保留注释/anchors)
- [x] 6.3 运行 `just qa` 与 `just openspec-check` 确保门禁通过
- [x] 6.4 扫描并升级仓库内示例/fixtures(例如 docs 代码块、tests YAML 片段、examples 目录等)到新语法,避免“文档与实现漂移”
