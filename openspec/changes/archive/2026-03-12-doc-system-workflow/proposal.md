## Why

当前仓库的“文档/规范/说明/技能(Skill)/Agent 指令”已经具备**局部自动生成**能力(例如 YAML DSL schema、skill references、文档区块注入),但整体仍存在高维护成本与易漂移问题:

- **来源分散**: 同一事实(如 Python 版本边界、构建命令、生成入口)在 `AGENTS.md` / `CLAUDE.md` / `docs/doc/**` / `openspec/specs/**` 多处重复出现,容易不一致。
- **生成边界不统一**: 既有 `.gen.json/.gen.md` 的全文件生成,也有 `<!-- BEGIN AUTOGEN:... -->` 的区块注入,但缺少“通用且强约束”的仓库级规范,导致 agent/贡献者很难稳定判断“该改哪里/该跑什么生成器”。
- **文档站点维护成本偏高**: `docs/doc/**` 中有大量与 schema/CLI/规范强耦合的 reference 内容,每次语义变更需要多点同步,且很难用 CI 自动兜底。
- **后续演进需求**: 计划引入 prompt 评测/调优(如 promptfoo)来持续改进 skill 与 agent guidance,需要先确立可校验、可注入、可回滚的文档治理基线。

因此需要把已有的“局部最佳实践”升级为一套**长期可维护、成本可控、可自动校验**的通用文档体系与工作流规范。

## What Changes

- 建立仓库级 **Doc Taxonomy(文档分层)** 与 **Ownership(责任边界)**:
  - 事实/约束优先沉淀在代码与规范(SSOT: single source of truth)
  - reference 自动生成; guide/教程保留手工维护
  - 明确 change/spec/manual/generated 的职责与链接方式
- 统一 **生成物命名与鉴别**:
  - 生成文件统一使用 `*.gen.*`(如 `.gen.md/.gen.json/.gen.yaml`)
  - 对手工文档中的“受控注入区块”,统一使用 `<!-- BEGIN AUTOGEN:<id> -->` / `<!-- END AUTOGEN:<id> -->`
  - 生成物必须带可追溯的“生成入口提示”(脚本名/just 目标)
- 为文档站点补齐“可控生成”的 reference 输出形态:
  - 在 `docs/doc/` 内引入受控的 `*.gen.md` reference 页面(例如 schema/CLI/规范索引),并在 nav 中显式收录
  - 手工 guide 页面只保留高层叙事 + 指向 generated reference 的一层直达链接(必要时通过标记区块注入小片段)
- 增加自动化兜底与 CI/QA 漂移防线:
  - 把文档生成/注入统一收敛到 `just gen-docs`(并由 `just gen` 调用)
  - 为 `docs/doc/**/*.gen.md` 与注入区块增加 drift check,并纳入 `just qa`/CI
- 明确 agent 协作规范:
  - 在 `AGENTS.md` 增补“生成物/注入区块”规则,要求 agent 避免直接编辑 `*.gen.*` 与受控区块
  - 在 `openspec/config.yaml` 增补 OpenSpec 工件写作规则: proposal/design/tasks 必须显式声明“哪些文档是生成的/哪些是手工的/生成入口是什么”

## Capabilities

### New Capabilities
- `doc-governance`: 定义仓库文档分层、生成边界(`*.gen.*` + `AUTOGEN` 区块)、更新工作流与漂移校验的规范。

### Modified Capabilities
- `docs-site`: 更新文档站点规范,允许并约束 `docs/doc/` 内受控 `*.gen.md` reference(同时保持站点“人工可读 + curated”的边界),并纠正与当前 Zensical 配置不一致的表述。

## Impact

- 受影响目录/文件(预期):
  - `docs/doc/**`(引入/调整 generated reference 与注入区块; 精简重复 reference)
  - `scripts/**`(增加/收敛 docs 生成入口与 drift check)
  - `AGENTS.md` / `CLAUDE.md`(补充并消除关键事实漂移)
  - `openspec/config.yaml`(补充文档治理上下文与 per-artifact rules)
  - `openspec/specs/docs-site/spec.md`(规范更新) + 新增 `openspec/specs/doc-governance/spec.md`
  - `justfile`(增加 `gen-docs`/`docs-drift-check` 等入口并纳入 `qa`)
- 不涉及运行时行为变更;本 change 目标是治理与流程,以降低后续语义变更的文档维护成本。
