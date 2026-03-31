## Context

仓库当前在 `src/scalim/vendor/yamlx/` 下同时 vendors 了 `PyYAML` 与 `ruamel.yaml`,但 `src/scalim/` 的运行时代码、统一 loader、workflow loader、CLI validate、位置索引与若干 tests 仍然直接依赖 `PyYAML` 风格 API 与节点类型。与此同时,仓库已经存在对 vendored `ruamel.yaml` 的实验性验证基础,并且项目未来可能需要更贴近 YAML 1.2 的解析语义、round-trip 编辑能力、以及注释/格式保留能力。

这不是一次适合“直接替换 import”的改动。`ruamel.yaml` 0.18.x 已移除若干顶层 `PyYAML` 风格 API,而仓库又必须继续满足 Python 3.6、vendors 同步、自包含导入链路、统一错误结构与现有样本 YAML 的稳定解析。该设计因此必须优先收敛迁移边界、阶段划分与验证 gate,并明确哪些文档是手工 SSOT、哪些生成物不得直接手改。

手工维护的 SSOT 包括本 change 下的 OpenSpec 工件、`src/scalim/vendor/README.md` 与 `src/scalim/vendor/yamlx/SOURCE.md`。若后续实现导致 docs site 或规格索引需要更新,应通过 `just gen-docs` 刷新生成物,而不是手工修改 `.gen.` 文件或注入区块。

## Goals / Non-Goals

**Goals:**

- 定义一个 repo-owned YAML facade,使业务代码不再直接绑定 `PyYAML` / `ruamel.yaml` 的第三方顶层 API 形状。
- 允许迁移分阶段推进: 先补 facade 与验证,再根据届时分析结果决定是否在同一 change 内切换默认后端。
- 保持 demand/workflow/CLI validate/imports 的重复键策略、位置索引、ErrorEnvelope 与 vendors 同步约束。
- 将 Python 3.6 下的 vendored runtime smoke checks 与真实 YAML 样本回归纳入默认后端切换 gate。
- 为未来基于 `ruamel.yaml` 的高级 YAML 操作保留扩展空间,但不强制第一阶段一次性交付。

**Non-Goals:**

- 不要求本 change 第一阶段立即提供完整 comment-preserving 编辑 API 或面向用户的 round-trip 写回功能。
- 不承诺在当前代码形态下直接把所有 `yaml.safe_load/load/compose/dump` 调用机械替换为 `ruamel` 原生调用。
- 不把 `notebooks/marimo/` 或 `packages/scalim-misc/` 提升为 Python 3.6 兼容目标;它们只作为 YAML 样本与行为回归参考,不是 runtime py36 契约的一部分。

## Decisions

### 1. 先引入仓库自有 facade,再考虑默认后端切换

直接把默认入口从 `yamlx.yaml` 指到 `ruamel.yaml` 会让现有大量 `PyYAML` 风格调用面立刻失效。因此迁移必须先通过仓库自有 facade 吸收第三方 API 差异,把 `safe_load` / duplicate key / compose / dump / location index / parse error 提炼为仓库定义的稳定契约,再让 facade 内部选择具体 vendored backend。

备选方案:
- 直接在 call site 上把 `PyYAML` 调用改成 `ruamel.YAML(...)`: 改动面分散,后续维护成本高。
- 在 vendored `ruamel` 上模拟一层完整 `PyYAML` 顶层 API: 初期看似省事,但会持续复制第三方兼容包语义,维护风险更高。

选择 facade 的原因是它既能支撑 staged migration,也能为未来高级 YAML 能力提供单一扩展点。

### 2. 默认后端切换不是 proposal 创建时就强制承诺的结果

该 change 明确允许“先完成分析、适配层与验证套件,再判断是否切换默认后端”。若届时分析发现 Python 3.6、样本语义、dump 稳定性或某些关键入口仍存在不可接受差异,则本 change 可以先交付 facade 与验证基线,默认后端切换由后续子任务或 follow-up change 决定。

备选方案:
- 在 proposal/design 阶段直接承诺本 change 必须完成默认切换: 风险过高,且会让 tasks 过早绑定当前代码细节。

### 3. 将真实 YAML 样本与 py36 smoke 验证纳入切换 gate

单纯 API smoke test 不足以证明可切换。默认后端切换必须以真实样本 YAML 为 gate,至少覆盖 `tests/fixtures/*.yaml`、`notebooks/marimo/**/declared_yaml_dsl/*.yaml` 与 runtime 关键入口的 Python 3.6 smoke checks。这样可以及早暴露 YAML 1.1/1.2 差异、imports/allowed roots 问题、dump 风格漂移和 duplicate key 行为差异。

备选方案:
- 只跑 unit tests: 无法覆盖样本 YAML 语义漂移。
- 只跑 notebook end-to-end: 会混入 `scalim-misc` 的 3.10+ 依赖边界,不能作为纯 runtime 证据。

### 4. 第一阶段不把高级 round-trip/comment 保留写成硬交付

用户价值上,`ruamel.yaml` 的高级能力很重要,但第一阶段的核心目标仍是“可安全迁移默认后端”。因此 design 只要求保留扩展点,不要求第一阶段就交付完整 comment-preserving authoring surface。否则会把 parser migration、authoring API 设计、docs 与 editor UX 一次性耦合到同一个 change。

## Risks / Trade-offs

- `[API facade 过窄]` → 若 facade 只覆盖当前最小用法,后续迁移仍可能在隐藏 call site 上泄漏第三方 API。缓解: 先做接入面 inventory,再定义 facade 边界。
- `[Python 3.6 与 ruamel 上游支持边界不一致]` → vendored 代码与 clib 可在本地 smoke 通过,但仍需要仓库自有 py36 gate 持续兜底。缓解: 将 py36 smoke 写入任务与 spec。
- `[YAML 1.1/1.2 语义差异]` → 真实用户 YAML 可能依赖 `yes/on/no` 或旧数字解析习惯。缓解: 在默认切换前对真实样本与 fixtures 做 corpus 对拍,并记录 blocker。
- `[dump 输出漂移]` → 即使 load 结果一致,序列化风格也可能改变。缓解: 把 dump style / alias 行为纳入 analysis 与 parity 检查。
- `[文档与规范漂移]` → 当前部分 specs 和 vendor 文档显式写死 `yamlx.yaml`。缓解: 先改 OpenSpec 与手工 SSOT,若实现期有 docs 变更再通过生成入口刷新。

## Migration Plan

1. 盘点当前 `src/scalim/` 内部所有直接依赖 `PyYAML` / `ruamel` 的调用面、类型耦合与错误假设。
2. 用真实 YAML 样本与 Python 3.6 smoke checks 建立 parity 基线,确认默认切换前必须满足的 gate。
3. 设计并实现 repo-owned facade/adapter,使业务层不直接依赖第三方顶层 API。
4. 将统一 loader、workflow loader、CLI validate/imports 等入口收敛到 facade。
5. 在 gate 全部通过后再决定:
   - 若风险可接受,启用 vendored `ruamel.yaml` 为默认后端。
   - 若仍有 blocker,保留 facade 与验证基线,把默认切换拆到 follow-up。
6. 默认切换完成后,再评估是否单独推进 comment-preserving / round-trip authoring 能力。

回滚策略:

- 在 facade 引入完成后,默认后端切换必须可回退到先前 vendored backend,且不要求回滚业务层调用代码。

## Open Questions

- 默认后端切换后,仓库是否仍需长期保留 vendored `PyYAML` 作为 fallback/compat backend,还是允许在验证完成后彻底移除?
- location index 与 node traversal 最终是继续基于 compose tree 统一实现,还是为 `ruamel` 单独实现更稳定的 traversal 逻辑?
- 是否需要在后续 follow-up 中提供显式的 “round-trip editing” 公共工具 API,还是先限制在内部 authoring/tooling 使用?
