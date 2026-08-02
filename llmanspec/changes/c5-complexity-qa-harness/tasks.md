# Tasks: c5-complexity-qa-harness

> 加塞规划壳；**尚未** `change start`。优先于 c20/c30 apply。

## 0. Specs landing（start 之后）

- [ ] 0.1 改写 `governance-module-organization` r253：复杂度 MUST + LOC SHOULD；更新 scenario
- [ ] 0.2 `llman sdd validate` strict

## 1. 基线

- [ ] 1.1 脚本可复跑：对 ENTRY（今日 `_HOTSPOT_LIMITS` 路径）采 cognitive + cyclomatic max
- [ ] 1.2 钉死 `MAX_COGNITIVE` / `MAX_CYCLOMATIC`（基线 + 3..5）；写入脚本常量 + evidence 摘要
- [ ] 1.3 （可选）LOC_HARD_TASTE≈2500 是否启用：按 proposal Q2

## 2. 门禁实现

- [ ] 2.1 新增 `scripts/check-complexity.py`（`--check` / `--radar` / `--quiet`）
- [ ] 2.2 `check-module-size.py`：硬失败降级为 SHOULD/报告；或仅保留硬味天花板
- [ ] 2.3 `justfile`：qa/quick-check 接复杂度硬闸；`just complexity` 雷达
- [ ] 2.4 `.gitignore`：`.tools/`（若本地 pin）
- [ ] 2.5 governance 单测更新 quiet/fail 合约

## 3. 文档

- [ ] 3.1 `docs/doc/dev/` 短文：阈值 SSOT、与 C901 pragma 关系、如何放宽
- [ ] 3.2 AGENTS.md Pointers 可加一行（可选）

## 4. 验证

- [ ] 4.1 ENTRY 当前树 `--check` 绿
- [ ] 4.2 人为压低 max → 非零 + 热点表
- [ ] 4.3 `just quick-check-only-py-no-test-gate` 含新闸且不回归无关门禁
