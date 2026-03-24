## Context

仓库当前已经形成多层“对外看起来可用”的入口：

- 顶层包根 `scalim`
- YAML DSL facade `scalim.dsl.by_yaml`
- workflow 辅助模块 `workflow` / `workflow_types` / `workflow_paths`
- 更底层的 `runtime.*` / `config_parsing.*` / `schema_dsl.*`

这些路径在技术上并不等价，但现有文档、specs、示例与测试门禁对“哪个是稳定公开入口”约束不够统一，容易让内部实现路径被误当成公共契约。

另一个问题是 `template_sandbox=legacy` 仍存在于默认公共 API 的形状中。它虽然已有风险提示，但本质上仍是把不安全放宽能力挂在默认官方 facade 上，和“严格约束、严格内聚”的目标冲突。

约束与前提：

- 本 change 只创建 change 工件，不实现真实代码逻辑。
- 假设更高优先级 change 先合并：
  - `framework-metadata` 已先稳定最小顶层 metadata 入口；
  - `workflow-layering-refactor` 已先稳定 workflow 公共入口与内部 runtime 分层；
  - 本 change 不重复定义这两个 change 的实现边界。
- `src/scalim/` 运行时后续实现必须兼容 Python 3.6。
- `.gen.*` 文件与 `AUTOGEN` 注入区块不得手改；真实实现阶段若需要更新 docs，必须走对应 SSOT 与 `just gen-docs`。

## Goals / Non-Goals

**Goals:**

- 把 YAML DSL 与库侧“稳定公开入口”定义成显式目录，而不是隐式依赖当前包结构。
- 将 public surface gate 分成正向白名单和反向回归检查，避免内部路径再次渗入 docs、skills、examples 与示例套件。
- 明确本轮收敛不等于删减受支持的扩展能力：`sink`、`components`、`output_composition` 仍保留在官方 facade。
- 将 `template_sandbox=legacy` 从默认公共 API 移除，并把“不安全能力必须显式 unsafe 化”写成长期治理规则。

**Non-Goals:**

- 不新增新的顶层公共 facade。
- 不在本轮删减 `run/compile` 的受控扩展点。
- 不重新设计 workflow 分层、output model 或 hook/observer 机制。
- 不在本轮直接修改 docs 主线、tests 或 runtime 实现代码；这些属于后续实现阶段。

## Decisions

1. **用“公共目录 + 非公共目录”双边界治理 public surface**

   不把“当前能 import”视为自动公开。后续实现阶段以一份 curated catalog 作为正向白名单，并把 `runtime.*` / `config_parsing.*` / `schema_dsl.*` 作为默认非公共目录处理。

   选择这个方案而不是继续依赖包结构直觉，是因为当前仓库既有 facade，也有大量为了内部拆分而保留的显式子模块；单纯靠文件位置无法表达“对用户是否承诺稳定”。

2. **保留能力，收紧入口**

   本轮不把 `sink`、`components`、`output_composition` 等既有受控扩展点从公开 API 删除；只把它们统一收敛到被明确承诺的 facade 上，并把 docs/examples/gates 从内部路径迁走。

   这样做比“顺手删参数”更稳，因为用户明确要求不要把这次变更扩大为真实能力剪枝，目标是减少公共表面扩散，而不是减少当前受支持功能。

3. **把 unsafe 能力治理成长期规则，而不是只修单点参数**

   `template_sandbox=legacy` 是本轮要落地的具体 BREAKING 变更，但设计上不只处理这个单点。规范层同时要求：未来任何放宽安全边界的能力都必须带显式 `unsafe` 语义，不能直接继续放在默认 facade。

   这样后续新增 escape hatch 时也能复用同一治理规则，而不是每次再补一轮专项 hardening。

4. **门禁采用多层组合，而不是只靠 `__all__`**

   后续实现阶段的回归门禁分为三层：

   - facade `__all__` / import smoke，保证正向公开目录可稳定导入；
   - examples / marimo public API suite，保证教学与用户可见用法走稳定入口；
   - docs / skills / tests 的内部路径漂移检查，保证不会把实现细节重新推广成事实公共 API。

   仅靠 `__all__` 不足以防止示例和文档继续引用内部路径，因此必须叠加反向检查。

5. **变更边界以 OpenSpec SSOT 为中心，真实 docs 更新延后到实现阶段**

   本次只创建 `openspec/changes/c20-public-api-surface-hardening/**`。主规范 SSOT 仍是 `openspec/specs/**/spec.md`；真实实现阶段若要同步 docs，必须从手工 SSOT 出发，并通过 `just gen-docs` / `just openspec-check` / `just qa` 做漂移校验。

## Risks / Trade-offs

- [规范先行但实现后置] → 当前 change 只定义未来实现边界，不会立即消除代码中的旧入口引用；通过 tasks 明确后续迁移与 gate 落点。
- [与更高优先级 change 交叉] → 在 proposal/design 中显式假设 `framework-metadata` 与 `workflow-layering-refactor` 已先合并，避免重复定义其边界。
- [公开面收紧带来 BREAKING 升级] → 后续实现阶段采用“一次性升级仓库内所有示例/测试/skills，不做兼容 shim”的策略，符合仓库的一步到位原则。

## Migration Plan

1. 先按本 change 的 delta specs 固定 public surface 规则与 legacy sandbox 收紧规则。
2. 真实实现阶段先升级官方 facade 与契约，再同步 tests/examples/docs/skills。
3. 最后加上 public-surface gates，并用 `just openspec-check`、`just qa` 验证。

## Open Questions

- 无。本提案按“保留既有受控扩展点、只收紧默认公共表面与 unsafe 能力”收敛，不再额外打开输出路径、workflow 语义或 facade 扩张相关决策。
