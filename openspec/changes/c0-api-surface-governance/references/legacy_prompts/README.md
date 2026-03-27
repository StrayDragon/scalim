# scalim API 表面治理 — Codex 执行提示词

基于 `source_plans/` 中 6 份原始方案合并筛选后的推荐路径，拆分为可逐步执行、逐步验证的 Prompt 序列。

## 目录结构

```
_PROMPTS/
├── README.md                         # 本文件
├── P0_api_surface_audit.md           # 只读分析探针
├── P1_incremental_all_seal.md        # __all__ 增量封堵
├── P2_barrel_fill.md                 # Barrel __init__.py 填充
├── P3_file_move_rename.md            # 文件移动/重命名
├── P4_types_module.md                # 新建 types.py 聚合入口
├── P5_external_import_migrate.md     # 外部导入路径迁移
└── source_plans/                     # 原始方案（Prompt 的决策依据）
    ├── 1_api_surface_governance.plan.md
    ├── 2_typedefs_audit_plans.plan.md
    ├── 3_re-export_chain_audit.plan.md
    ├── 4_package-encapsulation-refactor.plan.md
    ├── 5_dependency_boundary_decoupling.plan.md
    └── 6_api_compatibility_strategy.plan.md
```

## 原始方案 → Prompt 来源映射

| Prompt | 主要来源 | 采纳的决策 |
|--------|----------|------------|
| **P0** 分析探针 | 方案 1 审计数据 + 方案 3 数据基底 | 综合所有方案的分析维度 |
| **P1** `__all__` 封堵 | **方案 1** 决策点 2/3 + **方案 4** 泄漏清单 | 方案 1-A: 仅从 `__all__` 移除 `_` 前缀；方案 1-A1: `_internal` 补 `__all__=[]` |
| **P2** Barrel 填充 | **方案 3** 决策 4 + **方案 4** barrel 模板 | 方案 3-B: Selective barrel；方案 1-A: sinks 成为第六官方入口 |
| **P3** 文件移动 | **方案 4** 方案 C（混合策略）+ **方案 1** 决策点 3 | sinks→`_internal/`；events/hooks→`_`前缀；utils→`_internal/`；spec/ir→`_`前缀 |
| **P4** types.py | **方案 2** 方案 B（新建 types.py） | typedefs 保留为内部 SSOT，types.py 聚合 re-export |
| **P5** 导入迁移 | **方案 6** 领域四 R4 + **方案 3** 决策 1C | Codegen shim 暂缓，先做手动迁移对齐推荐路径 |

### 被裁剪的方案及理由

| 被裁剪项 | 来源 | 理由 |
|----------|------|------|
| 方案 4-B 纯 `_internal/` | 方案 4 | 对小包(events 4 文件)过重，混合策略(C)更务实 |
| 方案 2-D 激进重构 | 方案 2 | 68 文件改动，留给 major version |
| 方案 3-A 强制 barrel | 方案 3 | 260 处 import 迁移成本过高 |
| 方案 5-A runner 包 | 方案 5 主题 4 | 大规模重构，用"标注 integration layer"更务实 |
| 方案 5-A instrumentation 包 | 方案 5 主题 3 | ob→hooks 是合理设计，接受现状 |
| 方案 6-CI2 签名级 diff | 方案 6 | 复杂度高，先用 `__all__` snapshot 起步 |

## 执行顺序与依赖

```
P0_api_surface_audit.md      ─── 分析探针（只读）─── 产出 .tmp/api-surface-audit-report.md
         │
         ▼
P1_incremental_all_seal.md   ─── Phase 0: __all__ 封堵 ─── 分 5 批，每批 ≤10 文件
         │                        每批后 just qa ✓
         ▼
P2_barrel_fill.md            ─── Barrel 填充 ─── sinks → events → hooks，每包后 just qa ✓
         │
         ▼
P3_file_move_rename.md       ─── 文件移动/重命名 ─── 每包独立，前后快照对比，just qa ✓
         │
         ▼
P4_types_module.md           ─── types.py 新建 ─── 独立验证，just qa ✓
         │
         ▼
P5_external_import_migrate.md ── 外部导入迁移 ─── tests/ → packages/ → notebooks/，每批 just qa ✓
```

## 核心防护原则

- **每批 ≤10 文件**：限制爆炸半径
- **每步 `just qa`**：门禁即时验证
- **不改测试逻辑**：只改 import 行
- **TYPE_CHECKING 专项检查**：每个 Prompt 都有类型安全检查清单
- **失败即回退**：不尝试修复测试来适应改动
- **前后快照对比**：确保 API 表面不变

## 参考

- 原始方案文件：`source_plans/` 目录
- 项目门禁：`just qa`
- 项目约束：Python 3.6 兼容、ruff 格式化、相对导入
