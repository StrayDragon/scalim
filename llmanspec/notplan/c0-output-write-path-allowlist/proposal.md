# Proposal: output-write-path-allowlist

> 一句话描述: 为输出写入路径引入可选的 `allowed_output_roots` 白名单，堵住相对路径逃逸 YAML 目录的路径穿越风险（默认 `None`，向后兼容）。

## 与 c20/c30 关系

- **不被取代**。本 change 管输出 path 白名单（`allowed_output_roots`），与 `c20`（write_defaults/budget → Python）主题不同。
- 同碰 `yaml-dsl-books-resources` / `workflow-shared-output-containers`：合 delta / 实现时避免互相覆盖；本能力本身是 Python/runtime 入口，与「YAML 编排瘦身」方向一致。
- 相关归档：`llmanspec/changes/archive/2026-07-12-c20-book-write-policy-python-ssot/`、`.../2026-07-12-c30-workflow-shared-book-memory/`。

## Why

YAML **读取路径** 有完善的约束（`allowed_yaml_roots`、`validate_resolved_yaml_path_within_roots`、import 路径归一化），但**输出写入路径**无任何限制。`resolve_yaml_relative_output_path()` 中相对路径如 `../../sensitive/file.csv` 可解析到 YAML 目录之外，在多租户或不受信任的 YAML 作者场景下构成路径穿越风险。

## What Changes

1. **添加 `allowed_output_roots` 参数**：在 `resolve_yaml_relative_output_path` 和 `resolve_output_container_path` 中引入可选的输出路径根白名单
2. **路径验证函数**：复用或参考 `validate_resolved_yaml_path_within_roots` 的模式，验证解析后的输出路径在允许的根目录内
3. **DSL 编译层集成**：在 `compile()` / `run()` 入口暴露 `allowed_output_roots` 选项
4. **默认行为不变**：`allowed_output_roots=None` 时行为与现在一致（向后兼容）

## Capabilities

### Modified Capabilities

- `yaml-dsl-file-resources` — 输出路径约束
- `yaml-dsl-books-resources` — workbook/sheetbook 输出路径约束
- `workflow-shared-output-containers` — workflow 输出路径约束

### New Capabilities

（无新 spec，扩展现有 spec）

## Impact

- **代码区域**: `src/scalim/dsl/yaml_dsl/runtime/output_path_resolve.py`, `src/scalim/workflow/resources_base.py`, DSL 编译入口
- **破坏性**: 无 — 默认 `allowed_output_roots=None` 保持现有行为
- **安全**: 从 High 降为 Low（写入路径获得与读取路径对等的保护）
