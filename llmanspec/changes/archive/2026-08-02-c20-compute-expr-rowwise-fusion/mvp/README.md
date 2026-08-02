# MVP：N×M「框架税」举例（c20）

## 一句话

当有 **N 行**、**M 个**很薄的 `call_by`，且它们常依赖**同一小撮**上游字段时，总开销近似：

```text
成本 ≈ N × M ×（取依赖 + 调一次 Python 函数 + 写回）
```

函数体若只是 `a + b` 或格式化，**函数体本身很轻**；变慢的是外面那一层被乘了 `N×M` 次。这就是 c20 要减的「框架税」（尤其是**同一行内反复取同一批依赖**）。

c20 **不**把 M 次调用合成 1 次（那是另案 multi-output）；融合后仍是每字段每行调用一次，但改成：

```text
对每一行:
  依赖只取一遍（union / 相同 deps）
  再依次调用 field_0 … field_{M-1} 的计算器
```

---

## 具体小例子（数字）

假设一批里有 **2 行**，**3 个**派生字段，都依赖主表的 `v0`、`v1`：

| 字段 | 用户函数（都很薄） |
|------|-------------------|
| `d0` | `lambda v0, v1: (v0 or 0) + (v1 or 0)` |
| `d1` | `lambda v0, v1: (v0 or 0) - (v1 or 0)` |
| `d2` | `lambda v0, v1: (v0 or 0) * (v1 or 0)` |

### 今天更接近的执行（field-major）

```text
算 d0:  行0 取 v0,v1 → 调用 → 写回； 行1 取 v0,v1 → 调用 → 写回
算 d1:  行0 取 v0,v1 → 调用 → 写回； 行1 取 v0,v1 → 调用 → 写回
算 d2:  行0 取 v0,v1 → 调用 → 写回； 行1 取 v0,v1 → 调用 → 写回
```

- 计算器调用次数：`2 行 × 3 字段 = 6`（合理，值语义需要）
- **取依赖次数**：大约 `6 × 2 = 12` 次字段读取（每个调用读 2 个依赖）

### c20 目标形态（row-wise，deps 相同）

```text
行0: 取一次 (v0,v1) → 调 d0 → 调 d1 → 调 d2
行1: 取一次 (v0,v1) → 调 d0 → 调 d1 → 调 d2
```

- 计算器调用次数：仍是 **6**（与现在相同）
- **取依赖次数**：大约 `2 行 × 2 依赖 = 4` 次（再按字段复用）
- 另外少掉「按字段整列扫」时的一层调度摊销

把 2×3 换成 MVP 里的 **数千行 × 数十字段**，乘数就变成可测的端到端差距。

---

## 和「缓存 / cached_call_by」的差别

| | c20 融合 | memo / 将来的 `call_by`+开关 |
|--|----------|------------------------------|
| 打什么 | 薄 × 多字段的重复取依赖与调度 | 贵计算 + 依赖值跨行重复 |
| 调用次数 | 不变 | 可变少 |
| 用户改脚本 | 通常不用 | 要标哪些字段可缓存 |

已决议：**不**新增 `cached_call_by` 并列关键字。

---

## 本目录脚本

```bash
# 仓库根目录；开发环境
uv run python llmanspec/changes/c20-compute-expr-rowwise-fusion/mvp/repro_nxm_framework_tax.py

# 或 Python 3.6
PYTHONPATH=src .tmp/venvs/py36-scalim/bin/python \
  llmanspec/changes/c20-compute-expr-rowwise-fusion/mvp/repro_nxm_framework_tax.py
```

默认把 `result.json` 写到同目录 `evidence/<timestamp>/`。

脚本会跑三类对照：

1. **wide_many_call_by**：N 行 × M 个同 deps 薄 `call_by`（现状引擎）
2. **narrow_few_call_by**：同 N，但 M 很小（说明「字段个数」本身很伤）
3. **micro_loop_field_major vs micro_loop_row_wise**：纯 Python 微循环，直观展示「同 deps 时 row-wise 少读多少次」（**上界直觉**，不是已实现的引擎融合）
