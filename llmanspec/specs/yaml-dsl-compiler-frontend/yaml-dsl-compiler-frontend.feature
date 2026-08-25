# language: zh-CN
# capability: yaml-dsl-compiler-frontend
# purpose: 定义 YAML DSL 编译前端的两个步骤：静态编译（只解析 YAML/AST、不导入用户代码、不依赖 allowlist）与运行时链接（resolve modules + 执行 allowlist 约束）。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: yaml-dsl-compiler-frontend

  @req:r109 @human
  场景: Front-end compilation MUST build ExecutionPlan without importing user code
    - 系统 MUST 提供一个编译前端入口（front-end compilation），将单个 demand YAML 编译到： - diagnostics（errors/warnings，含稳定 path + range） - 静态 IR（不包含任何 Python callable） - ExecutionPlan 与依赖索引（可用于“字段上游依赖展开”等 dev features） 编译前端 MUST 满足： - MUST NOT 导入/执行任何用户模块（仅允许文件系统读取 + YAML/AST 静态解析）。 - MUST NOT 依赖 allowlist（allowlist 仅属于运行时解析与执行边界）。 - MUST 在失败时降级为可诊断结果（不 crash、不退出）。

  @req:r351 @human
  场景: Runtime linking (resolution) MUST be the only phase that imports modules and MUS
    - 系统 MUST 定义一个显式的运行时 linking（解析）步骤，用于把静态引用解析为可调用对象（loader / params_builder / normalize.call_by 等），并满足： - MUST 仅在运行时 linking（解析）步骤执行模块导入与 callable 解析。 - MUST 在解析时强制执行 allowlist 约束（不允许隐式放宽）。 - MUST 在解析失败时返回可诊断的错误分类（例如 allowlist violation / resolver error），并 fail-fast 于执行之前。
  @req:r109 @human
  场景: a-valid-demand-yaml-produces-a-plan-without-allowlist
    - 必须成立：假如 一个语义正确的 demand YAML（包含 sources/fields/relations 等定义）；当 调用编译前端入口生成 `ExecutionPlan`；那么 系统 MUST 返回 `ExecutionPlan` 与依赖索引
    假如 一个语义正确的 demand YAML（包含 sources/fields/relations 等定义）
    当 调用编译前端入口生成 `ExecutionPlan`
    那么 系统 MUST 返回 `ExecutionPlan` 与依赖索引
  @req:r351 @human
  场景: allowlist-violation-fails-during-runtime-resolution-before-e
    - 必须成立：假如 YAML 中存在一个 Python reference 需要解析为 callable；当 系统执行运行时 linking（解析）步骤；那么 系统 MUST 失败并给出可诊断的错误信息
    假如 YAML 中存在一个 Python reference 需要解析为 callable
    当 系统执行运行时 linking（解析）步骤
    那么 系统 MUST 失败并给出可诊断的错误信息
