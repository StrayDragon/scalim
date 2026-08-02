# Design: complexity QA harness（替代 LOC 硬闸）

## 分层

```text
HARD   just qa / quick-check
         scripts/check-complexity.py --check
         ENTRY = 今日 module-size 热点路径
         max over functions: cognitive ≤ A, cyclomatic ≤ B

SOFT   just complexity --radar
         更广 src/scalim top-N；exit 0

SHOULD LOC 报告（原 check-module-size 改警告为主）
OPTIONAL   LOC ≥ 2500 → 仍可失败（硬味天花板；已决议）
KEEP       ruff C901 + check-noqa-c901（r645）
ENTRY      = 今日 `_HOTSPOT_LIMITS` 路径（已决议）
TOOLS      = radon (cyclo) + cognitive-complexity 包（已决议）
```

## 实现要点

1. **采基线**：对 ENTRY 跑 radon + cognitive-complexity，写入 `mvp/evidence/baseline-entry.json`（可复跑脚本）。
2. **脚本**：`check-complexity.py` 仿 `check-module-size` 的 `--check` / `--quiet` 合约；工具缺失时 pin 到 `.tools/` 或 `uvx --from`。
3. **接线**：`justfile` `quick-check-only-py-no-test-gate`：用 `check-complexity` 替换硬 `check-module-size`；保留 `report-module-size`。
4. **Specs**：改 r253 表述与 scenario；合约数字与脚本常量同数。
5. **测试**：`tests/governance/` 扩 quiet/fail 合约（仿 `test_check_quiet_contract`）。

## 非目标

- 全仓 HARD。
- 用 cccc-rs 扫 Python（当前不可用）。
- 借机大规模拆分烫点函数（radar 债另开）。

## 与 c20/c30

本 change **加塞**优先合入，避免后续实现再被 LOC 硬闸逼出噪音拆分。不阻塞其设计；实现顺序建议：`c5` → `c20` → `c30`。
