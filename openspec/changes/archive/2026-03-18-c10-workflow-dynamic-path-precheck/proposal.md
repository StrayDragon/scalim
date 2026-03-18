## Why

下游在 workflow + YAML DSL 的组合使用中遇到“明明 DSL 已支持 `{$init_var: ...}`，但 workflow 侧却表现为不支持/误报冲突”的问题：

- demand 已支持在 `outputs.*.container.path` 使用 `{$init_var: <name>}` 注入路径；但 workflow 的 reserved/collision 预检查阶段会把 `container.path` 直接 `str(...)`，导致：
  - `{$init_var: output_path}` 这种 mapping 被当成同一个“字面字符串路径”参与碰撞检测，出现误报（假 collision）。
  - reserved-path 检查也会出现误判/漏判（未按 `init_vars/$ctx` 渲染后的最终路径判断）。
- 结果是下游被迫在 Python 入口做字符串替换 + 生成临时 `.runtime.demand.yaml` 文件来绕过检查，增加胶水代码与临时文件泄漏风险。

workflow 规范本身已经要求：当路径依赖 `init_vars/$ctx` 等动态渲染时，应在 node 物化编译后、实际写入前做 fail-fast（而不是依赖 `str(dict)` 的静态扫描）。因此需要一个高优先级修复，让实现与规范对齐，并让错误更确定、可诊断。

## What Changes

- 调整 workflow 的 Excel 输出路径 reserved/collision 检测策略：
  - 若路径可在结构编译阶段静态确定（纯字符串），允许在结构编译阶段 fail-fast（保持原有“尽早失败”体验）。
  - 若路径依赖 `init_vars/$ctx`（例如 `{$init_var: output_path}`），预检查 MUST 在 node 物化编译后、实际写入前 fail-fast，并使用渲染后的最终绝对路径参与判断。
- 修复 reserved-path 检查：当 workflow 声明共享输出资源（`resources.workbooks[*].path` / `resources.sheetbooks[*].export_xlsx.path`）时，禁止 demand 直接写该路径的判断必须基于“最终解析路径”而非原始 YAML 节点字符串化结果。
- 错误信息与确定性：
  - collision/reserved 的错误 MUST 指出 `run_id`、最终路径与冲突节点集合，且触发时机与顺序可复现（不依赖线程调度完成顺序）。

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `workflow-sheetbook-resources`: 补齐并落地“动态渲染路径（`init_vars/$ctx`）场景下的 reserved/collision fail-fast 时机与判定基准”为可测试的要求与实现对齐。

## Impact

- 受影响代码：
  - `src/scalim/dsl/by_yaml/runtime/workflow_entrypoints.py`（reserved/collision 预检查逻辑）
  - 可能涉及 `src/scalim/dsl/by_yaml/runtime/output_composition_yaml.py`（路径解析逻辑复用/提取）与 `src/scalim/dsl/by_yaml/init_var_nodes.py`
- 受影响测试：
  - 新增/调整 workflow 级测试覆盖 `{$init_var: ...}` 与 `$ctx` 参与路径解析的碰撞/保留路径检测。
- 文档/规范边界：
  - SSOT 规范位于 `openspec/specs/workflow-sheetbook-resources/spec.md`。
  - 本 change 下的 `openspec/changes/c10-workflow-dynamic-path-precheck/specs/**` 为增量规范草案；归档前应通过同步流程合并进 SSOT，并用 `just openspec-check` 做校验门禁。

