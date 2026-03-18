## Context

当前 workflow 在 `_compile_workflow_ir()` 阶段会加载每个 demand YAML，并对其中 `type: workbook` 的 `container.path` 做静态扫描以进行：

1) reserved xlsx path 检查（是否命中 `workflow.resources.workbooks/sheetbooks` 声明的路径）  
2) collision 检查（跨 run 是否写入同一路径）

但该扫描实现使用 `str(getattr(container, "path", "") or "")`，当 `container.path` 为 mapping 节点（例如 `{$init_var: output_path}`）时会退化为 `"{'$init_var': 'output_path'}"` 这种字符串，从而导致：

- 把不同 run 的动态 path 错误地聚合为“同一路径”（误报 collision）。
- reserved 检查无法基于最终渲染路径判断（误判/漏判）。

与此同时，workflow 在运行阶段已经具备：

- workflow-level `init_vars`（`run_workflow(..., init_vars=...)`）
- node-level `workflow.runs[*].init_vars`，并支持 `$ctx` 指令在依赖闭包内引用上游 node 的运行摘要（例如 `output_path/total_rows/duration_secs`）。

因此“完全 compile-time 静态预检查”在语义上并不完备：当路径依赖 `$ctx` 时，只有在依赖节点完成后才能解析。

## Goals / Non-Goals

**Goals:**
- 保证 reserved/collision 检查的判定基准为“最终渲染后的绝对路径”，而不是原始 YAML 节点的字符串化结果。
- 满足规范：静态可提取时尽早失败；动态依赖 `init_vars/$ctx` 时在 node 物化编译后、实际写入前 fail-fast。
- 保持确定性：同一 workflow YAML + 相同输入条件下，触发错误的顺序与报告信息稳定可复现。

**Non-Goals:**
- 不改变 demand 的输出语义（例如 demand 直接写 xlsx 仍然是“生成整本 workbook 并原子替换”）。
- 不引入新的 workflow YAML authoring surface（写节点表达力升级属于独立提案）。
- 不在本提案中引入“无路径内存输出”或管道式行流直连写节点（属于后续提案）。

## Decisions

### D1. 将动态路径的 reserved/collision 检查下沉到运行期（node compile 前）

决定：保留 `reserved_xlsx_paths` 的静态收集（来自 workflow resources），但将“扫描 demand 输出路径并进行 reserved/collision 判定”的逻辑从 `_compile_workflow_ir()` 的全量静态扫描，迁移到运行时每个 demand node 的物化编译前：

- 在 `_try_submit_ready()` 中，demand node 会先渲染并合并 `init_vars`（包含 `$ctx` 渲染结果），再调用 `compile_demand(...)`。
- 在调用 `compile_demand(...)` 之前（或紧邻其内部、能拿到最终 init_vars 的位置），解析该 demand 的 workbook 输出路径集合：
  - 对 `container.path`：
    - `str` → 直接使用
    - `{$init_var: name}` → 从已渲染的 `init_vars[name]` 解析为非空字符串（支持 `str|os.PathLike`）
  - 对 meta/audit 的 workbook path（若存在）沿用相同解析策略；若 meta/audit 未显式声明 path，则沿用“默认 workbook path”策略（保持兼容既有行为）。
- 将解析后的路径归一化为绝对路径（`expanduser + resolve(strict=False)`）后进行判定：
  - 若命中 `reserved_xlsx_paths` → fail-fast（提示 run_id + path）
  - 若与已登记的其它 run 冲突 → fail-fast（提示 path + nodes）
  - 否则登记 `abs_path -> node_id`

理由：
- `$ctx` 依赖的值只能在运行时依赖闭包完成后获得，运行期检查是语义完备的最早时机。
- 编译（而非执行/写入）阶段即可获得最终输出路径，仍满足“实际写入前 fail-fast”。
- 由于 `_try_submit_ready()` 在主线程串行执行编译（仅执行被提交到线程池），因此登记表无需复杂并发控制且顺序稳定。

替代方案（不选）：
- 在 `_compile_workflow_ir()` 中遇到动态节点即跳过或仅 warning：会导致运行期晚失败，且错误归因更差。
- 允许动态节点参与静态碰撞：会继续产生误报（当前问题）。

### D2. 保留静态预检查但只覆盖“可静态确定”的路径

决定：在 `_compile_workflow_ir()` 中仅对“显式字符串路径”做静态 reserved/collision 检查（可选，作为性能优化与更早 fail-fast）；对含 `{$init_var: ...}` 的 path 不做错误判断，只做结构校验。

理由：
- 不丢失“尽早失败”的用户体验（静态路径仍可在编译阶段报错）。
- 避免对动态节点做错误推断。

## Risks / Trade-offs

- [额外 I/O] 运行期可能需要再次读取 demand YAML 来提取路径 → 缓解：复用 `compile_demand` 已加载的 config/compilation 结果，或在 loader 层暴露“输出路径摘要”以避免双读。
- [错误时机变化] 原先在 workflow compile 阶段就失败的动态节点，现在会在运行期 node compile 前失败 → 缓解：错误仍在写入前 fail-fast，且更语义正确；并在错误 message 中明确触发阶段与路径。
- [确定性] 多个 ready 节点并发时可能导致检查时机受调度影响 → 缓解：编译/登记发生在主线程，ready_queue 按声明顺序稳定排序，因此 determinism 可保证。

