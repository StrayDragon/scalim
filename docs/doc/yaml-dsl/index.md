# YAML DSL

??? note "适用读者"
    - 写 YAML 配置的使用方开发者/数据运营/数据同学
    - 维护 schema/编辑器补全的项目贡献者

## 主线原则(上位约束)

YAML DSL 的主线演进遵循以下上位原则(后续提案/变更默认不得违反):

- **单主线原地演进**: 不引入 `dsl_version`、不维护并行 parser/validator/schema
- **`YAML = authoring`**: YAML 聚焦可移植的 authoring surface
- **`Python/CLI = runtime policy`**: 环境/性能/集成策略等 knobs 优先收口到运行入口
- **KV-first**: 需要稳定 ID/引用/复用的结构优先 mapping;仅顺序具业务语义时用 list
- **workflow 小而声明式**: workflow 不扩张为 imports/片段组合系统

**YAML vs Python 边界速查**（c40 已落地：动态 knobs 收口 Python typed oneof）:

- 评审速记: [提案审核清单](review-checklist.md)
- 能力表: [YAML→IR 能力矩阵](capability-matrix.md)
- Agent 边界: `agentdev/skills/scalim-yaml-dsl/references/yaml-runtime-policy-boundary.md`
- Upgrade（`lookup_chunk_size` → `LookupChunking`）: `agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-08-09-lookup-chunking-python-ssot.md`
- 图边 vs 目录（c50：`to_source_id` / overlay 只写 `DemandIr.sources`）: `agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-08-18-source-id-graph-refs.md`
- 何时用 / 事件自证: `agentdev/skills/scalim-yaml-dsl/references/lookup-chunking-guidance.md`；oracle `ch164_public_api_lookup_chunking`
- 归档设计/证据: `llmanspec/changes/archive/*-c40-yaml-runtime-policy-boundary/`

提案/评审清单见: [YAML DSL 提案审核清单](review-checklist.md)

推荐阅读顺序(按使用目的):

- 写配置/跑起来: [语法速查](syntax.md) → [用户指南](user-guide.md) → [编辑器](editor.md)
- 想从 Python 侧调用/集成: [公共 API 导入指南](../getting-started/public-api.gen.md)
- 想理解 YAML 与 IR/运行入口的边界: [YAML→IR 能力矩阵](capability-matrix.md)
- 看一条端到端主线 demo(含对拍/排错命令): [主线教程: demo_big_data_report](../getting-started/demo-big-data-report.md)
- 编排多条 demand: [Workflow](workflow.md)
- 升级旧写法/破坏性变更: [升级指南](upgrades/index.md)
- 想让智能助手协助写/改 YAML: [集成AI环境 (Agent Skill)](agent-skill.md)
- 维护 schema/编辑器补全: [Schema Meta 参考](schema-meta.md)

下一步:

- [并行模式(seq/adaptive)](../architecture/parallel-modes.md)
