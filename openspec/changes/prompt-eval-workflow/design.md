## Context

仓库内的 skill、agent 指令与文档治理规则属于“高杠杆文本资产”: 一次改动可能导致路由错误、用例回答质量回退、误改生成物/注入区块等问题,且这些回归往往难以靠常规单元测试覆盖。

因此需要引入一套可复现的 prompt 评测/回归工作流,把关键交互用例固化为自动化评测,并提供稳定入口用于本地与 CI 运行,同时把结果以确定性方式输出到受控目录以便回归对比。

**Status: DELAYED**

该 change 当前标记为 **DELAYED**: 在 `openspec/changes/README.md` 移除 DELAYED 标记之前,不得开始实现。

## Goals / Non-Goals

**Goals:**
- 提供稳定的仓库级入口: `just prompt-eval`。
- 评测流程可在本地一键运行,并可在 CI 中运行(初期可作为非阻塞 job)。
- 评测结果以确定性方式输出到受控目录(建议固定在 `.tmp/artifacts/prompt-eval/`)便于上传与对比。
- 评测集覆盖 doc governance 的关键边界用例:
  - 不修改 `*.gen.*` 文件
  - 不修改 `AUTOGEN:*` 注入区块内容
- 在实现前收敛文档/生成边界: 明确哪些内容必须手工维护,哪些必须生成,哪些是 injected-block,以及对应的生成/校验入口与 drift gate。

**Non-Goals:**
- 不引入 `src/scalim/` 运行时依赖变化(仅允许 dev/CI 侧依赖)。
- 不在本 change 内一次性做“全量 prompt 质量评测/调优”(先落可回归的最小集合与工作流骨架)。
- 不强制把 prompt-eval 立即升级为 CI 门禁(先跑通与积累用例,再评估门禁策略)。

## Decisions

### Decision 1: 分层评测(确定性核心 + 可选模型评测)

为满足“可复现 + CI 可运行”的底线,评测分两层:

1) **确定性核心评测(默认总是运行)**  
   - 不依赖外部模型/密钥/网络
   - 以规则/策略/静态校验为主,用于守护边界与关键约束(例如 doc governance)
2) **可选的模型驱动评测(按需启用)**  
   - 在本地或具备密钥的 CI 中运行
   - 用于覆盖“路由/回答质量”一类只能通过模型交互验证的回归

动机: 让 `just prompt-eval` 在任何环境都能产出稳定信号(只跑确定性 core),并为后续增量引入模型评测预留扩展位(例如 `just prompt-eval-llm`)。

### Decision 2: 统一运行器与用例组织方式

- 新增一个仓库级运行器脚本(建议放在 `scripts/` 下,例如 `scripts/prompt_eval.py` 或 `scripts/prompt_eval/run.py`),由 `just prompt-eval` 调用(确定性 core)。
- 用例以“数据驱动”的方式组织(例如 `openspec/prompt-eval/cases/` 下的 YAML/JSON),每个用例包含:
  - `id` / `title`
  - `kind`(policy/router/llm 等)
  - `inputs`(例如要评测的提示词/任务描述/候选 diff fixture)
  - `assertions`(确定性断言或评分规则)

该结构保证用例可增量扩展,并且评测结果可以稳定序列化输出。

### Decision 3: 模型评测层采用 `promptfoo`(可选层)

- 模型评测层选用 `promptfoo`(Node) 作为 runner,但必须保持**可选**: 不把 Node 工具链变成 `just prompt-eval` 的硬依赖。
- `promptfoo` 的启用方式建议二选一(实现时定一种并固定下来):
  1) 独立入口: `just prompt-eval-llm` (明确需要密钥/网络/Node)
  2) 同入口开关: `just prompt-eval` + 环境变量 `PROMPT_EVAL_LLM=1`
- 版本与行为必须可复现: `promptfoo` 版本 pin,并固定模型参数(例如 `temperature=0`)。

### Decision 4: doc governance 边界用例的“可机械评测”策略

为了把“不可修改 generated / injected-block”变成可回归用例,确定性核心评测引入两类验证器:

- **Generated 文件边界**: 任何变更触达路径匹配 `*.gen.*` 的文件都应被判定为违规(除非用例明确允许,默认禁止)。
- **Injected-block 边界**: 任何 diff 触达 `<!-- BEGIN AUTOGEN:<id> -->` 与 `<!-- END AUTOGEN:<id> -->` 之间内容都应被判定为违规。

用例形式(确定性核心):
- 以“diff fixture(补丁/变更清单)”作为输入,校验验证器能稳定识别违规/非违规。

后续扩展(可选模型评测):
- 用同一套验证器去校验模型/agent 产生的真实 diff,确保边界规则在端到端交互中也能守住。

### Decision 5: 结果产物边界与 drift gate

为了可对比与可上传,评测输出收敛到受控目录,并保证确定性:

- 输出目录: `.tmp/artifacts/prompt-eval/`
- 建议的稳定文件名:
  - `summary.json`(总览: 用例数、通过/失败、耗时、版本信息)
  - `cases.jsonl` 或 `cases.json`(逐用例明细)
  - `failures.md`(可读的失败摘要,包含修复建议)
- 所有输出 MUST 保持确定性:
  - 稳定排序
  - 稳定序列化(避免时间戳进入对比口径;如需记录时间,放入非对比字段或另存)

drift gate 策略(最小可行):
- prompt-eval 自身提供 `--check` 模式(或单独 `just prompt-eval-check`),用于在 CI 中只做校验与产物生成,不做交互式写入/修复。
- 模型评测层的输出建议独立子目录(例如 `.tmp/artifacts/prompt-eval/llm/`),并在早期仅作为“观察信号 + CI artifact”,不进入强制漂移门禁。

### Decision 6: CI 集成方式(先非阻塞,可升级)

- 新增 CI job 运行 `just prompt-eval`
- 上传 `.tmp/artifacts/prompt-eval/` 作为构建产物
- 初期作为非阻塞(allow-failure/continue-on-error),待用例覆盖与稳定性达标后再评估升级为门禁

## Risks / Trade-offs

- [模型评测不可完全确定性] → 默认只把确定性核心作为硬信号;模型评测先做非阻塞/仅用于观察与回归定位,并通过固定参数(如 temperature=0)降低抖动。
- [用例维护成本上升] → 以最小集起步,优先覆盖“边界规则 + 高频路由场景”,并把用例组织为数据驱动以便扩展。
- [工具链复杂] → 核心层保持 Python-only;模型层按需引入,避免把 Node/外部工具变成硬依赖。
- [误把生成/注入边界写死导致开发体验变差] → 通过“明确例外机制”(仅当用例声明允许时)与清晰失败提示(指向 `just gen-docs` 等入口)缓解。

## Migration Plan

1) 落地确定性核心评测 + `just prompt-eval` 入口 + 受控输出目录。
2) 增加最小用例集,覆盖 spec 要求的 doc governance 边界回归。
3) 增加 1-2 个“路由/引用材料选择”类用例(可先用确定性断言占位),为后续模型评测铺路。
4) 引入可选模型评测并在 CI 中先以非阻塞方式运行,积累稳定性数据后再评估是否门禁。

## Open Questions

- `promptfoo` 的版本 pin 方式选哪种更符合仓库习惯: `package.json` devDependency、`npx promptfoo@<pinned>`、还是在 `scripts/` 内提供安装/缓存策略?
- `promptfoo` 配置文件放哪里作为 SSOT(例如 `openspec/prompt-eval/promptfoo/` 或 `scripts/prompt-eval/promptfoo/`)?
- 默认 provider/模型如何配置(本地/CI),密钥如何注入,以及 CI 中是否需要“有密钥/无密钥”两条路径?
- 模型评测的回归口径怎么定:
  - 哪些用例允许波动(只作为观察)?
  - 哪些用例可升级为门禁(需要阈值/多次稳定)?
  - 是否需要版本化黄金输出/评分基线,以及如何降低模型更新导致的漂移成本?
