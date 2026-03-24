## Context

当前已实现的 `workflow-managed-temp-outputs` 允许 pathless CSV outputs 在 workflow 中被 writes 消费，但具体实现仍是：

- workflow 为 output 注入一个 run-scoped 临时 CSV 路径
- demand 节点把结果写到该临时路径
- write nodes 再把这个 CSV 读回，写入共享 workbook/csv/sheetbook
- workflow 结束时清理 managed temp dir

这个设计满足语义，但它把“中间态仅供 workflow 内部消费”的数据仍然降格成磁盘文件，增加了 IO、路径管理和清理成本。

约束：

- 假设 `workflow-layering-refactor` 已先合并，workflow runtime 的 SSOT 已下沉到 framework 层；本设计按该目标分层表述。
- `src/scalim/` 运行时必须兼容 Python 3.6。
- v1 只处理 workflow-managed pathless CSV outputs，不扩展到 parquet/json/sqlite、spill、预算治理或跨 demand source 复用。
- 文档/规范 SSOT 仍以 `openspec/specs/**/spec.md` 为准；本 change 不修改 `.gen.*` 与 `AUTOGEN` 注入区块，验收仍走 `just openspec-check`。

## Goals / Non-Goals

**Goals:**

- 去掉 workflow-managed pathless CSV outputs 的临时落盘路径，让 workflow 与 demand 之间通过内存中间态传递数据。
- 保持现有 workflow YAML 写法不变，尤其是 `outputs[*].container.path: ""` + `writes[*].*.output` 的 authoring surface。
- 保持普通文件输出、standalone demand 的 path 校验规则、write nodes 的资源写入语义不变。
- 在 workflow 中为内存中间态提供明确的发布、消费、释放边界，避免整次 workflow 执行结束前无限保留。

**Non-Goals:**

- 不引入内存预算、spill-to-disk/tmpfs、LRU、OOM 防护。
- 不支持非 CSV 的 workflow-managed pathless outputs。
- 不在本 change 处理中间态跨多个 demand 节点作为 source/lookup 直接复用。

## Decisions

1. **新增稳定的 `InMemoryCsv` artifact 形态**

- 引入一个简单、可序列化理解的内存表结构：表头 + 已对齐的字符串行。
- 该结构只服务于 workflow 内部 artifact 传递与 write nodes 消费，不作为新的公共 DSL 配置面。
- 选择“已字符串化的 CSV 语义”而不是保留原始 `RowData`，是为了最大限度复用现有 `csv/workbook/sheetbook` 写入逻辑，保持与当前 CSV 中间文件语义等价。

2. **workflow 对 pathless CSV 的授权采用显式 allowlist，而不是隐式推断**

- workflow 在 demand 节点编译/装配时，显式声明哪些 output_id 属于 workflow-managed outputs。
- 只有在该 allowlist 内的 pathless CSV outputs 才允许编译通过并走内存 sink。
- standalone demand 保持现有 fail-fast 规则，不因为运行时新增内存 artifact 能力而放宽约束。

3. **output composition 负责物化内存 sink，workflow runtime 负责接收与分发 artifact**

- pathless CSV target 的 sink 仍在 execution/output composition 层创建，因为它本质上属于 output 装配的一部分。
- `ExecutionResult` 需要把这类内存 outputs 显式暴露回 workflow runtime。
- workflow runtime 不重新实现一套 demand 输出写出逻辑，只接收运行结果中的 memory outputs，并把它们发布为 workflow artifacts。

4. **write nodes 同时支持 `file-backed output` 与 `in-memory output` 两种输入**

- `csv/workbook/sheetbook` 资源管理实现统一抽象“读取 header / 迭代行”的输入协议。
- 这样普通文件 output 与内存 output 共用同一套对齐、append、commit、discard 逻辑，避免复制语义。
- 这是对现有 write path 的扩展，不引入新的 workflow node 类型。

5. **内存释放按“最终 write consumer 完成”触发**

- workflow 编译或执行准备阶段预先推导 `(producer_node_id, output_id) -> remaining_write_consumers`。
- 每个 write node 成功消费后递减计数；计数归零时立即释放该内存 artifact。
- 选择按最终消费者释放，而不是“workflow 结束统一释放”，是为了在不引入预算系统的前提下降低峰值常驻内存。

## Risks / Trade-offs

- [峰值内存上升] 去掉中间落盘后，较大的 CSV 中间态会驻留内存，v1 又不做预算限制 -> 通过“最终消费者后立即释放”降低常驻时长，并把预算/spill 留给后续 `workflow-intermediate-store-optimizations` 提案。
- [语义漂移风险] 若内存 sink 的字符串化规则与现有 `CSVSink` 不一致，可能导致 workbook/csv/sheetbook 写入结果变化 -> 内存 artifact 必须复用与 CSV sink 等价的值规范化规则。
- [分层回归] 若 workflow runtime 直接入侵 execution/output internals，后续与 `workflow-layering-refactor` 容易打架 -> 通过 `ExecutionResult` 暴露明确返回值边界，避免 workflow runtime 私下探测 sink 内部状态。
- [多消费者释放过早] 同一 output 可能被多个 write intents 消费 -> 采用显式 consumer 计数，而不是第一次消费后立即删除。

## Migration Plan

- workflow YAML 无需迁移；已有 pathless CSV + writes 配置在实现后直接获得新语义。
- 依赖“读取 managed temp path”这一内部实现细节的测试/断言需要升级为检查：
  - write 结果仍正确
  - 不再生成 managed temp outputs 目录
- 若实现回退，只需恢复旧的 temp-path 注入与文件读回路径；不会影响用户 authoring surface。

## Open Questions

- `InMemoryCsv` 是否需要在 workflow 事件/调试输出中暴露规模摘要（例如 rows/cols），便于排障但不泄露数据内容。
- 若某个 write node 失败，失败路径是否需要立刻丢弃它已经不再可达的内存 artifact，还是统一交给 workflow 失败清理处理。
