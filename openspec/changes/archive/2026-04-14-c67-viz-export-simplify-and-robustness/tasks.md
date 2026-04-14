## 1. 契约收敛与回归护栏

- [x] 1.1 更新/补充 delta specs：明确 viz JSONL 在并发/重入下的“可解析性”与 single writer 契约（对齐 notplan 组 C）
- [x] 1.2 增强并发回归测试：覆盖 events/trace 两条 JSONL 输出在并发下逐行可解析，并覆盖 close/drain 边界

## 2. 实现：收敛 JSONL 写出为 single writer

- [x] 2.1 重构 `VizEventEmitter`：引入 single writer 边界（queue/worker 或等价 capture+replay），减少显式锁竞争
- [x] 2.2 保持输出格式不变（`vizevent/v1`、run_id/node_ref/payload_policy 等字段与文件路径约定）
- [x] 2.3 确保 snapshot 写入仍为 temp+replace 原子写（不引入 lockfile）

## 3. 性能与稳定性验证

- [x] 3.1 在不改变语义的前提下评估 flush 策略（先保持现状语义，再考虑批量 flush 优化点）
- [x] 3.2 运行 `just qa` 确保全仓库门禁通过，并确保 viz 相关回归测试稳定
