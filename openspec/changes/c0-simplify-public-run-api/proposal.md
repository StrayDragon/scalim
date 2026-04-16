## Why

当前公开运行入口(`scalim.dsl.yaml_dsl.run/compile/run_workflow`)围绕一个“超大 `RunOptions` + 若干 workflow 额外参数 + sink/outputs discovery”的组合语义，在热点链路上形成多处隐含规则与不一致点：

- 调用方需要记住大量“哪些参数在 demand 有效 / 在 workflow 无效”的约束，容易写错且难以做自动校验。
- 维护者在演进时需要小心维持历史组合语义（例如输出/tee/sink 相关的隐式装配），导致改动风险高、回归成本高。

本变更希望将运行期参数收敛为少量**正交、内聚、可被 runtime 校验**的结构化配置对象（先以 dataclasses 为主，设计上可平滑迁移到 Pydantic），并统一 demand/workflow 的输出与捕获语义，使 API 更容易使用、更不容易写错，且更利于长期维护。

## What Changes

- **BREAKING**：重构运行入口的 options-object 结构，拆分并内聚 runtime knobs，避免继续扩大“扁平 `RunOptions`”的公开字段集合。
  - 目标：将安全边界/模板编译期/执行期/输出策略/可观测性等关注点拆分为更小的子对象（仍保持“单一 options 对象驱动入口”的整体形态）。
- **BREAKING**：统一输出/保留语义，移除“通过传入一个参数隐式改变 sink 行为”的模式（典型问题：demand 在存在文件输出时，额外传入 `sink` 会触发隐式 tee，导致语义组合难以预测与维护）。
  - 目标：以显式、强类型的输出模式/捕获策略表达“是否写文件 / 是否保留内存 / 是否镜像(tee)”等选择，并与 workflow 保持一致的规则边界。
- **BREAKING**：收口 workflow 入口的 public surface，移除测试/注入型参数在公共 facade 中的暴露（例如 `run_ir_fn` / `compile_demand_yaml_fn` 这类注入点），改为 internal/test-only 边界，避免用户材料固化内部实现结构。
- 生成一份可审计的 “public API exports catalog” 快照（从 `src/scalim/**` 中声明 `__all__` 的模块扫描得到），用于本次简化讨论与后续门禁/文档同步的对齐材料（SSOT 仍以各模块 `__all__` 为准，不引入手工维护的符号级硬 manifest）。

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `dsl-runtime-structure`：更新运行入口与 options-object 的组织规则（保持“单 options 对象驱动”，但其内部从大平铺改为内聚分组，并强化可校验边界）。
- `workflow-run-patches`：per-run patch 模型需要与新的 options 分组对齐（哪些字段可 patch、三态语义、禁止覆盖安全边界等）。
- `output-mode-api`：调整输出/tee/capture 的表达方式，避免隐式语义组合；并明确 demand/workflow 的一致性约束。
- `public-api-surface-governance`：更新 curated entrypoints 的公共导出面（例如移除注入型参数暴露），并确保用户材料不固化内部路径。
- `marimo-example-public-api-suite`：更新 public API 覆盖套件，使其覆盖新的公开入口与最小闭环用法（并与 pytest public_api suite 保持一致）。

## Impact

- 受影响代码（预期）：
  - `src/scalim/dsl/yaml_dsl/*`：public facade、运行期契约、workflow entrypoints/types。
  - `src/scalim/execution/run_ir.py`：输出装配与 tee/capture 相关策略边界（若调整输出模式表达）。
  - `src/scalim/sinks/*`：公开使用方式与契约可能需要配合调整（实现细节不应泄漏到 API）。
  - `src/scalim/shortcuts/resources/outputs.py`：可能新增与运行结果对象的桥接用法（保持隐藏底层落盘协议）。
- 受影响用户材料（预期）：
  - `docs/doc/yaml-dsl/*`：示例与迁移指引。
  - `notebooks/marimo/example_public_api_suite/*` 与 `tests/public_api/*`：public API 回归覆盖。
- 工具链/治理（预期）：
  - public API exports catalog 的生成/对齐（与既有 `__all__` 治理脚本、用户材料导入边界检查共同构成门禁闭环）。
