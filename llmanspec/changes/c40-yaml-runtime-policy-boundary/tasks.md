# Tasks: c40-yaml-runtime-policy-boundary

> 重开。目标：全量盘点 → 闭合 R 切片 →（其后）`change start` 一步到位落地。  
> **禁止**在 inventory/design 写死「永久留 YAML」终局句。

## A. 盘点（进行中）

- [x] A.1 从 demand/workflow schema 导出全量 path（见 inventory §7）
- [x] A.2 对拍已迁出 fail-fast + Python-only 面（inventory §0）
- [x] A.3 重写 inventory/design/proposal：废止「暂不迁」；开放轴 A/C/R/M/X/?
- [ ] A.4 为每个 `R/?` 行补「为何可能动态」证据笔记（下游/部署/入口）
- [ ] A.5 核对 params 指令节点（`$keys`/`$rows.cache_mode` 等）无漏标
- [ ] A.6 机器可读全 path 导出脚本（可选，输出 `.tmp/`，不入库）

## B. 目标切片（盘点闭合后）

- [ ] B.1 列出拟定为 R 的键 + 拟议 Python API（覆盖 vs 硬迁出）
- [ ] B.2 兼容策略草图（fail-fast 窗 / 默认+覆盖优先级）
- [ ] B.3 文档/skill/upgrade 同发清单
- [ ] B.4 确认是否改 live MUST → 若是则 `change start` + specs landing

## C. 入口去定论（与盘点同步）

- [x] C.1 回调 AGENTS / yaml-dsl docs / skill「暂不迁/灰区终局」措辞 → 指向开放 inventory
- [x] C.2 自检：仓库内无「c40 结论：lookup_chunk_size 中长期留 YAML」类定论（入口已改；inventory 本身禁止写死）

## 门禁

- [x] 未 start 前不改 live `llmanspec/specs/**`、不改 schema 行为
- [ ] `just llmanspec-check` 在文档回调后通过
