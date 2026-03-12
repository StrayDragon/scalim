## Context

当前 YAML DSL skill 的主要问题不是“信息太少”,而是“生成边界错了”. 生成器同时负责 `SKILL.md`、reference 与示例,于是产物天然向 schema dump 倾斜,缺少面向真实任务的流程指引. 结果是:

- agent 能触发 skill,但不容易一次完成 YAML 编写、升级、校验和订正
- 自动提取出的 minimal/advanced 示例没有有效进入最终 skill 入口
- 业务侧真实迁移经验无法稳定沉淀,因为它们更适合手工维护的 playbook,而不是纯自动导出

这次变更跨越 `scripts/gen-agent-skill.py`、`packages/scalim-misc/src/scalim_misc/agent_skill_gen.py`、skill 目录结构、测试与文档,并且包含迁移策略与脱敏要求,需要先明确 manual/generated 的职责边界.

## Goals / Non-Goals

**Goals:**
- 将 skill 入口改为手工维护,让它真正面向任务而不是面向 schema dump
- 将生成器职责收敛为“生成并校验 generated references”
- 明确 CLI/LSP 指引,尤其是 `uv run` 与 `uvx --from "PROJECT_DIST_NAME[cli]"` 两套调用方式
- 沉淀一个脱敏后的 legacy 批量报表渐进迁移 playbook,帮助 agent 自动判断 YAML/Python 的职责边界
- 建立 manual/generated 边界测试,避免未来再次退化为“整包自动生成”

**Non-Goals:**
- 不在本 change 中直接实现所有新的 skill 文案内容以外的业务迁移器
- 不为旧 skill 目录结构保留兼容层;目录与命名允许直接升级
- 不在本 change 中扩展 YAML DSL runtime 能力本身,例如原生多 sheet 输出或跨行聚合

## Decisions

### Decision: Skill package split into manual core and generated references

skill 包将拆成两部分:

- manual:
  - `SKILL.md`
  - `references/task-authoring.md`
  - `references/task-upgrade-legacy.md`
  - `references/task-validate-debug.md`
  - `references/task-report-migration-playbook.md`
- generated:
  - `references/generated/syntax-catalog.md`
  - `references/generated/cli-lsp-reference.md`
  - `references/generated/example-full/ecommerce_report.yaml`
  - `scalim-yaml-dsl.build-manifest.json`

manual 部分由人维护,负责“何时读什么、怎么决策、怎么交付”; generated 部分由脚本维护,负责“把完整语法/API 与唯一 canonical example 稳定导出出来”.
`SKILL.md` 必须保持 routing-first: 只保留任务分类、最小 CLI 入口与对上述 references 的一层直达链接,不把完整 schema/API 或场景预设直接塞进 skill 正文.

之所以不继续让生成器产出 `SKILL.md`,是因为 skill 入口的价值在于任务分流和步骤约束,而这类内容依赖高层判断与真实使用反馈,天然不适合从 schema 自动拼接.

备选方案:
- 继续自动生成 `SKILL.md`,但加更多模板和后处理

拒绝原因:
- 仍然会把 task guidance 和 schema catalog 混在一起
- 生成逻辑会越来越脆弱,且难以表达迁移 heuristics

### Decision: Generator owns only `references/generated/` and manifest

`scripts/gen-agent-skill.py` 继续作为入口,但只驱动 generated references 的构建与校验.
`agent_skill_gen.py` 的受控输出集合缩小到 `references/generated/` 与 manifest.

生成器必须:
- 拒绝写入用户技能目录
- 只覆盖受控 generated 文件
- 不触碰 `SKILL.md` 与其它手工 references
- 在 validate 模式下仅比较受控输出的字节漂移

备选方案:
- 让生成器顺便检查并重写 manual references 中的部分片段

拒绝原因:
- 会重新模糊 manual/generated 边界
- 手工 playbook 极易被“自动修正”为低价值模板文本

### Decision: Use generated references for exhaustive syntax/API coverage

“列全所有 YAML DSL 语法和 API” 仍然是生成器的职责,但落点改为 generated catalog:

- syntax catalog: 来自 schema 顶层字段、definitions、metadata
- CLI/LSP reference: 直接来自 `src/IMPL_ROOT/cli/yaml_dsl.py` 与 canonical schema path,作为命令与 schema 查询方式的唯一详尽来源
- canonical example: 仅来自 `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`,导出到 `references/generated/example-full/ecommerce_report.yaml`

manual skill 只保留最关键的入口指引,例如:
- 仓库内: `uv run PROJECT_CLI_NAME ...`
- 脱离仓库: `uvx --from "PROJECT_DIST_NAME[cli]" PROJECT_CLI_NAME ...`
- schema path / `$schema` header 的直接提示
- 指向 task-specific manual references 与 generated references 的一层直达链接

完整 catalog 仍可按需读取,因此不会牺牲覆盖率,同时避免把 skill 入口变成 500+ 行 reference.

### Decision: Encode sanitized migration heuristics as a manual playbook

业务实践不会直接以真实项目名、路径、模块名进入 skill. 它们会被抽象成一种“legacy 批量报表脚本渐进迁移到 YAML DSL”的通用场景.

playbook 需要沉淀的不是具体业务对象,而是判断规则:
- 是否是大宽表 + 多 sheet 分发
- 是否需要 compare-friendly 双路由
- 哪些 loader 可以直接引用下游服务/BLL
- 哪些逻辑因 runtime state / aggregation / output 能力边界必须暂留 Python

playbook 只写“可迁移规律”和“决策标准”,不写真实系统名、绝对路径、业务字段名或私有 marker. 如需展示 marker、模块路径、入口函数或 loader 符号,统一使用脱敏占位示例.

备选方案:
- 完全不写业务侧场景,只保留通用 YAML DSL authoring 技巧

拒绝原因:
- skill 会再次脱离真实高价值任务
- agent 无法学会如何切分 YAML 与 Python 的职责边界

### Decision: Validate both generated content and manual contract

为了避免“手工维护 skill = 无法自动校验”,本次会把测试分成两层:

- generated tests:
  - generated references 是否可稳定重建
  - YAML 示例是否可通过 YAML DSL 校验
  - CLI/LSP reference 是否引用真实存在的命令与 schema path
- manual contract tests:
  - `SKILL.md` 是否存在
  - `SKILL.md` 是否包含 `uv run` 与 `uvx --from "PROJECT_DIST_NAME[cli]"` 两套命令
  - `SKILL.md` 是否链接到 required manual/generated references
  - 生成器不会覆盖 `SKILL.md`

这样既保留手工维护的自由度,又不放弃“真实可用”的自动校验.

## Risks / Trade-offs

- [manual 文档与代码发生漂移] → 用 contract tests 校验关键命令、链接、schema path 与生成器边界
- [generated 目录重构会影响现有引用路径] → 本次直接升级目录结构,同步更新 docs/test/just 相关引用,不保留兼容层
- [脱敏 playbook 过于抽象,失去指导价值] → 保留任务分类、边界判断和推荐结构,只删除项目名/路径/私有实现细节
- [manual references 增多,维护成本上升] → 让 `SKILL.md` 只做路由,高频任务只保留少数 3 到 5 份 manual references

## Migration Plan

1. 重构 `agent_skill_gen.py` 的输出布局,将受控输出迁移到 `references/generated/`
2. 停止生成 `SKILL.md` 与手工 guidance references
3. 手工重写 `artifacts/skills/scalim-yaml-dsl/SKILL.md` 与 task references
4. 为 generated references 与 manual contract 分别补测试
5. 更新 `scripts/gen-agent-skill.py`、相关 docs 与 `just` 任务说明
6. 执行 `openspec validate --all --strict --no-interactive`

回滚策略:
- 若 manual skill 尚未准备好,可暂缓删除旧产物并只保留 change 文档;不发布半完成的 skill 包
- 一旦进入实现,采用直接切换到新布局的方式,不额外维护旧 layout 兼容逻辑

## Resolved Details

- generated 侧只保留一个 canonical full example: `references/generated/example-full/ecommerce_report.yaml`; 不再生成 minimal / advanced / examples index.
- generated `cli-lsp-reference.md` 以 CLI 实现与 schema path 为唯一详尽来源; manual skill 只保留高频命令摘要,不重复完整命令目录.
- playbook 中涉及 compare 路由、marker、模块路径和 loader/BLL 符号时统一使用脱敏占位示例,表达的是一类报表迁移场景而不是具体业务实现.
