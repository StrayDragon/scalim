"""README 示例全局旋钮（用户可改后本地重跑）。

CI / `just examples`（example_readme_suite） 使用下方默认小 scale，保证门禁秒级完成。
相对内存图的提交资产来自 `chart_snapshot.json`（确定性），不是每次 CI 实测值。
"""

from __future__ import annotations

# --- 可调旋钮（本地演示可放大）---
N_ROWS = 1500
N_FIELDS = 48
BATCH_SIZE = 150
# 每个宽表字段的填充字节数：放大 naive 全量物化与 scalim 窄字段路径的对比
PAYLOAD_CHARS = 64

# 对比脚本默认只保留这几个输出字段（scalim 路径）
SCALIM_KEEP_FIELDS = ("order_id", "amount", "amount_x2")


def effective_knobs():
    # 预留：未来可用环境变量覆盖；当前与模块常量一致，便于注入到 README。
    return {
        "N_ROWS": int(N_ROWS),
        "N_FIELDS": int(N_FIELDS),
        "BATCH_SIZE": int(BATCH_SIZE),
        "PAYLOAD_CHARS": int(PAYLOAD_CHARS),
        "SCALIM_KEEP_FIELDS": list(SCALIM_KEEP_FIELDS),
    }
