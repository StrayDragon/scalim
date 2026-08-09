# Design: YAML vs Python policy boundary（c40）

## 目标态（一步到位方向）

把 YAML authoring 收敛为 **可移植的编排 + 资源身份 + 内容/数据流语义**；把 **部署/环境/入口可变** 的策略与调优 knobs **收口到 Python typed options**（可覆盖、可按 run patch），并在同一次变更集内对齐：schema fail-fast 或覆盖语义、runtime、docs、skill、upgrade。

本 design **不**固化「某键永久留 YAML」名单；去留以 `inventory.md` 开放轴 + 证据迭代，落地前再锁迁移切片。

## 与既往调研的关系

早期 R1–R3 曾倾向「灰区暂不迁」。该结论 **作废**，不再作为决策依据。保留其有用部分：

- 已迁出/已删除表（§0）仍是边界证据  
- 「大小 ≠ 并行」「两套 cache_mode 勿混」仍是语义事实  
- 错误做法：未盘点删键；回流 `write_defaults`/`budget`

## 判定启发式（工作用，非合约）

| 更像 A / C（YAML） | 更像 R（Python） |
|--------------------|------------------|
| 换环境仍应相同的图与字段语义 | 换机房/配额/DB IN 上限就会改 |
| loader 调用协议、关联路径 | 并发、重试、缓存寿命、分片大小、诊断 |
| 资源 identity / 输出形状 | book 写策略、staging、observers |

**优先按 R 评估的现网候选**（仍开放）：`sources.*.lookup_chunk_size`、`sources.*.cache_mode`；其次 `encoding` / `allow_formulas` / `outputs.write.*`（证据不足则保持 `?`）。

## 一步到位交付面（落地时）

1. **Inventory 闭合**：`inventory.md` 无未标轴顶层 knob；`?` 有证据或显式延期理由  
2. **Python surface**：凡定为 R 的键，有 `DemandRunOptions` / overrides / workflow patch 对等能力（或明确「删除能力」）  
3. **YAML**：迁出则 fail-fast + 迁移文案；若保留默认 + Python 覆盖，文档必须写清优先级（禁止静默忽略）  
4. **Docs/skill**：与 inventory 同向；禁止残留「暂不迁终局」话术  
5. **测试**：迁出/覆盖优先级/混称诊断各至少一条  

未 `change start` / 未绑分支前：**不改** live specs、不改 schema 行为。

## 非目标（当前阶段）

- 在调研文档里宣布最终去留名单  
- 复活 budget / Dedup / TwoStage / `write_defaults`  
- 把 `$rows.cache_mode` 与 `sources.*.cache_mode` 混成同一迁移包而不拆语义  

## 依赖与顺序

1. 闭合 inventory（本目录）  
2. 选定 R 切片 + Python API 草图（仍本目录 / 或后续 tasks）  
3. `change start` → specs（若改 MUST）→ apply  
4. 文档/skill 与代码同发  

可选后续（非本目标阻塞）：更细缓存策略扩展（只扩 Python）。
