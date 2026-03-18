## Context

当前 demand outputs 的 `container.path` 是强约束必填字段（schema + runtime 都会 fail-fast）。workflow 的 write nodes 则要求上游 demand outputs 落到 CSV 文件路径，再由 workflow 统一写入共享资源。

这在“最终输出文件路径明确”的场景没问题，但在“只作为中间 artifacts 给 write nodes 消费”的场景会带来额外负担：
- authoring 被迫填充一个临时路径；
- 下游往往在 Python 入口做替换/生成临时 demand YAML 来绕过；
- 临时文件的生命周期与清理语义不统一，存在泄漏风险。

同时我们必须坚持 Scalim 的目标：大表数据不应在节点间通过纯内存搬运；临时输出也应是磁盘 artifacts 并具备确定的清理边界。

## Goals / Non-Goals

**Goals:**
- 支持 workflow 托管临时 CSV outputs：允许在“被 write nodes 消费”的场景省略 `container.path`，由 workflow 分配实际路径并清理。
- 保持 fail-fast 与可诊断：漏配/误用必须在编译或物化编译阶段明确报错。
- 清理语义明确：workflow 成功 commit 或失败 discard 后，临时 outputs 必须被清理（避免泄漏）。

**Non-Goals:**
- 不支持“纯内存 output”把大表直接传给 write node（需要 backpressure/失败语义，复杂度很高）。
- 不支持 pathless workbook 输出（workbook 仍是最终落盘容器，必须显式路径）。
- 不把临时 outputs 写入 `$ctx`（ctx 仅用于小对象）。

## Decisions

### D1. 仅对 `type: csv` 支持 pathless，并要求被 write intents 引用

决定：当 `outputs[*].container.type == "csv"` 且 `container.path` 省略/为空时：
- 仅在 workflow 托管模式下允许；
- 且该 output_id 必须被 workflow write intents 引用（否则 fail-fast）。

理由：避免“无意漏填 path 但默默写临时文件”的错误，且与 workflow 写节点真实需求一致。

### D2. workflow 在 node 物化编译前分配 managed temp dir，并把真实路径注入编译

决定：在 workflow 的 compile-on-ready 阶段（node deps 满足后、调用 `compile_demand(...)` 前）：
- 创建 run-scoped 临时目录（建议位于 workflow artifacts 目录下，便于调试与集中清理）；
- 为被引用且 pathless 的 outputs 分配确定性的文件名（例如 `<output_id>.csv`）；
- 将这些路径注入到 demand 编译所用的输出装配逻辑中（推荐通过扩展编译选项/参数，而不是写临时 YAML 文件）。

### D3. 临时 outputs 的生命周期由 workflow 统一管理

决定：
- workflow commit/discard 后必须清理 managed temp dir；
- 在 `failure_policy=all_fail` 的提前终止路径也必须进入 finally 清理；
- 清理失败不得影响主流程返回，但应有可观测 warning（避免静默泄漏）。

### D4. schema 允许该写法，但把约束写进 hover 文案

决定：需求来自 workflow authoring，因此 schema 层必须允许用户写出该形态（否则 editor/schema validate 会拦截）。
但由于 JSON schema 无法表达“仅当被 write intents 引用时才允许”，因此：
- schema 允许 `path` 省略/为空（仅对 csv 容器）；
- hover 文案必须明确：该写法仅在 workflow 托管场景有效，单独运行 demand 会报错。

## Risks / Trade-offs

- [schema 放宽导致误用] 用户在 standalone demand 中省略 path：缓解 → 运行期 fail-fast + 清晰错误提示，文档强调边界。
- [清理语义复杂] 需要覆盖成功/失败/取消等所有分支：缓解 → 统一在 workflow finally 处理，并写测试锁住。
- [调试可见性] 临时文件被清理后难复现：缓解 → 提供可选开关保留临时目录（仅可信排障场景）。

