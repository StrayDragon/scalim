## Context

`frontend/scalim-yaml-dsl-editor/` 当前以 demand YAML 为中心进行补全/hover/校验与模板新建,并内置了 `demand.gen.json`。随着 YAML DSL 在仓内持续演进(例如 `outputs`、`imports/$import`、`workflow`、`normalize` 扩展与 runtime vars 写法收敛),编辑器侧会出现明显漂移:

- 默认模板与 outline/可视化面板仍以旧结构(例如 `output`)为核心,与新 schema 不一致
- schema 资源与发布物易在 `src/`、`public/`、`dist/` 之间漂移,引入“看似可用但校验不一致”的隐性问题
- workflow YAML 等新入口无法复用当前的校验/issue 定位链路

本 change 以“前端作者体验与 canonical schema 对齐”为核心,集中处理 editor 适配与治理边界。

## Goals / Non-Goals

**Goals:**
- 让 editor 的模板/outline/可视化编辑与仓内 canonical schema(生成物)保持一致,避免漂移。
- 将输出相关作者体验从单 `output` 模型迁移到 `outputs` 列表模型(至少覆盖最小可运行与稳定 roundtrip)。
- 让 editor 在不依赖 Python 环境的前提下继续提供可用的 schema-only 校验与 issue 定位。
- (可选) 为 workflow YAML 引入多 schema 选择/校验能力,并复用既有 issue 模型。

**Non-Goals:**
- 不在此 change 中推动后端 DSL 语义本身的演进(由对应 YAML DSL changes 负责)。
- 不做大规模 UI 重设计(保持现有交互体系,以适配与一致性为主)。
- 不引入新的重依赖(继续保持浏览器侧轻量与可离线运行的基本能力)。

## Decisions

1) **Schema 同步治理(SSOT)**
- editor 内置 schema MUST 仅来自既有生成入口(例如 `just gen-yaml-dsl-editor-schema`)。
- 目标是让 `frontend/scalim-yaml-dsl-editor/src/schema/*.gen.json`、`public/schema/*.gen.json` 与 `dist/schema/*.gen.json` 之间的一致性可被门禁兜底,避免手改与漂移。

2) **模板新建的默认写法与 breaking 策略**
- “从模板新建(最小模板)”的输出 MUST 与仓内 YAML DSL 的最新 authoring surface 对齐。
- 对于已确定的破坏性迁移(例如 `output` → `outputs`),editor 侧采取“一步到位”策略: 模板直接生成新写法,并在 UI/校验层提供可操作的升级提示。

3) **`outputs` 作者体验的最小闭环**
- 文本为 SSOT,可视化编辑通过补丁/预览确保 roundtrip 尽量稳定。
- 最小闭环优先覆盖:
  - 读取并展示 `outputs` 列表与 `name`/`container`/`fields`/`where`/`aggregate` 等关键字段
  - 能从可视化操作生成最小可运行的 `outputs` 配置(不要求覆盖全部高级字段)

4) **workflow YAML 的多 schema(可选)**
- 若引入 workflow YAML 校验,editor 需要支持对不同 schema 的选择与应用(至少 demand vs workflow)。
- 多 schema 方案应复用现有:
  - schema 加载策略(bundled + fetch fallback)
  - issue 统一模型与定位能力
  - exact(Pyodide)校验的可选链路(若适用)

## Risks / Trade-offs

- **变更面较大(模板 + outline + visual + validate worker)** → 通过分阶段落地与门禁(`just qa`)控制风险。
- **schema 漂移导致“前端可编辑但后端 fail-fast”** → 强制 SSOT 生成入口与 drift gate,并在 PR 前跑 `just gen`。
- **workflow 多 schema 改动过大** → 允许先落地 demand 侧的 `outputs/imports/normalize` 适配,将 workflow 作为独立阶段推进。

## Migration Plan

1. 先固化 schema 同步与发布物一致性(减少后续迭代的漂移成本)
2. 更新最小模板与示例,对齐新 authoring surface(`outputs`/runtime vars 等)
3. 适配 outline/可视化面板对 `outputs` 的读写路径(保证 roundtrip 与定位)
4. (可选) 引入 workflow 多 schema 选择与校验
5. 更新文档并通过 `just gen`/`just qa`/`just openspec-check`,完成归档
