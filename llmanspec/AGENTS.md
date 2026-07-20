# llmanspec AGENTS.md

此文件由根目录的 `AGENTS.md` 托管块引用。可在此添加项目特定的规则、
上下文或约定，以便 AI 代理遵守。

<!-- 在此行下方添加你的规则 -->

## 项目上下文
项目定义: 高性能(内存优先)报表生成框架,核心为 YAML DSL + IR 驱动执行.
目标能力: 多数据源关联、流式输出、可观测性与可视化事件流.
运行时需兼容 Python 3.6(开发通常 3.10+).
主要依赖: PyYAML、typing-extensions 兼容层;jsonschema/rich 为可选.
工程风格: Python-only,4 空格缩进,140 行宽,双引号.
命名规范: 函数/变量 snake_case,类 PascalCase.
`src/<主库>/` 内优先相对导入,避免 `from __future__ import annotations` 于核心运行时.
核心领域概念: Demand、Source、Field、Relation、Observability.
架构模式: Hook/Event 扩展机制 + Sink 抽象输出层.
测试基线: pytest + xdist;慢测使用 `@pytest.mark.slow`.
行为变更需同步 `llmanspec/specs/*/spec.md`.
文档治理规则: 任何包含 `.gen.` 的文件均为生成物(禁止手改);任何 `BEGIN/END AUTOGEN:<id>` 区块为受控注入区块(禁止手改区块内部).
文档生成入口: 优先运行 `just gen-docs` 刷新站内 `docs/doc/**/*.gen.md` 与注入区块;提交前由 `just qa`/CI 漂移门禁兜底.
llmanspec 工件在共享或发布前必须先运行 `llman sdd validate --all --strict --no-interactive`.
提交前缀建议: `feat:`、`refactor:`、`fix:`、`docs:`、`specs:`、`qa:`、`tests:`、`chore:`、`package/distribution:`、`sync:`、`tmp:`.
示例策略: 优先扩展现有 demo/YAML,再新增文件.
Active changes 命名规范(仅对 `llmanspec/changes/` 下未归档变更生效):
- 统一使用 `c<priority>-<kebab-case>` 形式,例如 `c10-workflow-ir-roadmap`
- `priority` 建议按 10 递增(预留 `c0-`/`c5-` 等插队位),便于从名称直观看出推进顺序,优先级越小越优先.
- `llmanspec/changes/archive/` 中的历史归档不做重命名
提案引用约定:
- 当在其它提案/文档中引用某个 change 时,仅使用其 `<kebab-case>` 名称(不带 `c<priority>-` 前缀),避免优先级调整导致跨文档引用漂移

### YAML DSL 主线原则(摘要)
当你在 `llmanspec/changes/` 下创建/评审 YAML DSL 相关变更时,默认遵循这些上位原则(完整 SSOT 以 `llmanspec/specs/governance-mainline-principles/spec.toon` 为准):
- 单主线原地演进: 不引入 `dsl_version`、不维护并行 parser/validator/schema, 版本管理只依赖pypi包版本
- `YAML = authoring`, `Python/CLI = runtime policy`
- KV-first: 需要稳定 ID/引用/复用的结构优先 mapping
- workflow 小而声明式,并拒绝 workflow imports expansion
- books: YAML 仅声明资源 identity（唯一分支 `xlsx`，可选 `path`→pathful / 无 path→pathless）；`xlsx_file`/`xlsx_memory` 已硬删（见 `.../2026-07-20-c999-remove-deprecated-xlsx-file-memory-kinds/`）；`write_defaults` 与 `budget` 以 Python 为 SSOT(勿回流 YAML 主线); 归档见 `llmanspec/changes/archive/2026-07-12-c20-book-write-policy-python-ssot/` 与 `.../2026-07-12-c30-workflow-shared-book-memory/`

### Spec 命名与架构层级规范
#### 标准层级前缀
创建新 spec 时,必须使用以下标准层级前缀之一:
**核心架构层级 (按数据流向)**:
- `yaml-dsl-*` - YAML DSL层：配置解析、验证、编译到IR
- `ir-*` - IR层：中间表示定义
- `planning-*` - 规划层：IR → ExecutionPlan 转换
- `execution-*` - 执行层：ExecutionPlan 执行
- `output-*` - 输出层：结果输出
**支撑和扩展层级**:
- `hooks-*` - 钩子系统：流程定制
- `observability-*` - 可观测性：监控和诊断
- `events-*` - 事件系统：事件定义和分发
- `workflow-*` - Workflow层：多节点编排
- `runtime-*` - 运行时系统：通用运行时行为
**工具和辅助层级**:
- `cli-*` - CLI工具层
- `tools-*` - 工具层：通用工具
- `testing-*` - 测试相关
- `quality-*` - 质量保证
- `governance-*` - 治理相关
- `vendor-*` - 供应商兼容层

## Artifact 规则
- proposal: 若变更涉及 docs/specs/skills,proposal MUST 明确: 哪些文件是 SSOT、哪些是生成物/注入区块,以及对应生成入口(脚本或 `just` 目标).
- design: design MUST 在实现前收敛文档/生成边界(哪些写手工,哪些生成,哪些是 injected-block)并给出 drift gate 方案.
- tasks: tasks MUST 对每个生成物/注入区块写清楚: SSOT、生成入口(优先 `just gen-docs`)与验收口径(例如 drift check/`just qa`).
- specs: spec 名称必须使用标准层级前缀之一: yaml-dsl-*, ir-*, planning-*, execution-*, output-*, hooks-*, observability-*, events-*, workflow-*, runtime-*, tools-*, testing-*, quality-*, governance-*, vendor-*
- specs: spec 命名应避免使用过宽的前缀（如 core-），应使用具体的层级前缀（如 execution-* 而非 core-execution-*）
