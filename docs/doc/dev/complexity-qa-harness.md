# 复杂度 QA harness

## 目的

用**函数级** cognitive(Sonar) + cyclomatic(McCabe) 硬闸替代「热点文件行数超阈即 QA 红」的主故事。行数降为 SHOULD 指导,仅保留极高硬味天花板防无底膨胀。

对齐 `governance-module-organization` **r253**;与 **r645**(ruff `C901` + `check-noqa-c901` / `allow-c901` plan)互补,不双 SSOT。

## 分层

| 层 | 入口 | 行为 |
|----|------|------|
| HARD | `just check-complexity` / `quick-check` | ENTRY 路径 max(函数) `cognitive ≤ 80` / `cyclomatic ≤ 44` |
| SOFT | `just complexity` (`--radar`) | 更广 `src/scalim` top-N; exit 0 |
| SHOULD | `just report-module-size` | 热点舒适区行数报告 |
| OPTIONAL | `just check-module-size` | 仅 `LOC_HARD_TASTE=2500` 硬味失败 |
| KEEP | `check-noqa-c901` + ruff C901 | 豁免须带可追踪 plan |

## 阈值 SSOT

常量钉在 `scripts/check-complexity.py`:

- `MAX_COGNITIVE = 80` (ENTRY 基线 max 75 + 5)
- `MAX_CYCLOMATIC = 44` (ENTRY 基线 max 39 + 5)
- `ENTRY_PATHS` = 原 `check-module-size` `_HOTSPOT_LIMITS` 路径集合

合约数字与脚本常量必须同数;放宽阈值须同步改 r253 表述并留下基线证据。

## 工具

- **radon** (`cc`): McCabe cyclomatic
- **cognitive-complexity**: Sonar cognitive

均为 CLI/脚本依赖(`uv run --with ...` / `uvx` pin);**不**进应用 `dependencies`。本地可选 pin 到 `.tools/`(已 gitignore)。

## 常用命令

```bash
just check-complexity
just report-complexity
just complexity
just report-module-size
just check-module-size
```

人为压低阈值应非零并打印热点表:

```bash
uv run --with radon --with cognitive-complexity python scripts/check-complexity.py \
  --check --max-cognitive 1 --max-cyclomatic 1
```

## 与 C901 pragma 的关系

- 复杂度硬闸看 **数值**;`# noqa: C901` 不能绕过 `check-complexity`。
- 保留/新增 C901 豁免仍须 `# pragma: allow-c901 <plan>`(见 `check-noqa-c901`)。
- 降复杂度优先:提取可单测规则函数 → 再考虑放宽 MAX_* 或缩 ENTRY。

## 如何放宽

1. 对 ENTRY 复跑基线(`--write-baseline`),确认新 max。
2. 将 `MAX_*` 设为 `基线 max + 3..5`(禁止抄行业默认 15 直接 HARD)。
3. 同步更新 r253 中的数字与本文档。
4. 验证:当前树 `--check` 绿;压低阈值非零。
