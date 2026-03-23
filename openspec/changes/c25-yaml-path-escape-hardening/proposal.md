## Why

当前 by_yaml 的多个“从路径读取 YAML”的入口存在目录穿越（`..`）/逃逸风险：路径被 `resolve()` 后未被约束在一个明确的“允许根目录集合”内，导致只要攻击者/误用者可控制 YAML 路径字符串，就有机会读取工作目录之外的任意 `.yaml/.yml` 文件（以及通过 symlink 进一步扩大读边界）。这在 CI/多租户/半可信配置输入场景中属于高危脚枪。

受影响面主要来自两类路径：

- demand YAML 的 `imports.<alias>` fragment 路径（`src/scalim/dsl/by_yaml/config_parsing/imports.py`）
- workflow YAML 的 `runs[*].demand` 路径与别名路径（`src/scalim/dsl/by_yaml/workflow.py`）

### 最小复现（imports 逃逸）

当前 `_normalize_import_path()` 允许 `../x.yaml`（并且不会限制能向上走多少级）；随后 `imports.<alias>` 通过 `(base_dir / normalized).resolve()` 得到最终路径，但没有检查该路径是否仍在“允许范围”内：

```py
from pathlib import Path

from scalim.dsl.by_yaml.config_parsing.imports import _parse_imports_mapping

base_dir = Path("/tmp/reports")  # 需求 YAML 所在目录
imports = _parse_imports_mapping({"secrets": "../../secrets.yaml"}, base_dir=base_dir)
print(imports["secrets"])  # => /tmp/secrets.yaml (或更上层，取决于 base_dir)
```

当 `secrets.yaml` 存在时，后续 imports expansion 会把该文件作为 YAML 片段加载并合并进 demand 配置。

### 最小复现（workflow demand 路径逃逸）

workflow 对 `runs[*].demand` 的解析允许相对路径（并直接 `resolve(strict=False)`），因此 `../../x.demand.yaml` 会被解析到 workflow 目录之外；同时还允许绝对路径与别名路径（更易误用到不受控路径）。

## What Changes

- **BREAKING**：为 “YAML 路径解析/加载” 引入统一的 allow-roots 策略（安全默认值）
  - 所有从 YAML 读取的路径（imports fragments、workflow runs demand、workflow path aliases）在 `resolve()` 后 MUST 通过 “是否位于允许根目录集合” 的校验
  - 默认允许根目录集合建议为：入口 YAML 所在目录（以及显式传入的额外 roots）；从而默认阻断任意层级的 `../` 逃逸
  - 需要跨目录复用（例如 `../_shared/common.yaml`）的用户，必须显式把对应目录加入 allow roots（“不太限制用户”的前提是显式声明信任边界）
- 兼容性与可用性护栏（避免过度限制）
  - 提供明确、可组合的配置入口：`allowed_yaml_roots` / `allowed_paths`（名称待 design 决定），支持传入多个目录
  - 提供可选开关：是否允许绝对路径（默认否）；是否允许 symlink 指向 root 外（默认否，避免 symlink 逃逸）
  - 错误消息必须包含：raw path、base_dir、resolved path、以及允许 roots 列表（便于快速定位误配置）
- 增加安全回归测试
  - `imports: {x: ../../secrets.yaml}` 在未配置 allow roots 时 MUST fail-fast
  - 当 allow roots 显式包含目标目录时，上述用例 MUST 成功
  - symlink 逃逸用例（root 内 symlink 指向 root 外）在默认策略下 MUST fail-fast

## Sequencing / Dependencies

- 建议作为 imports/paths 的安全基线尽早落地（在 `yaml-dsl-import-aliases-and-presets` 之前），并作为后续 aliases/presets 的 roots 校验复用点（避免出现两套“roots 语义”漂移）。

## Capabilities

### New Capabilities
- `yaml-dsl-allowed-paths-policy`: 定义 YAML 路径解析/加载的统一安全策略（allow roots、绝对路径策略、symlink 策略、错误诊断字段）。

### Modified Capabilities
- `yaml-dsl-imports`: imports v2 的路径规则需要与 allow-roots 策略对齐；`../` 仅在显式允许的 roots 范围内可用（从“任意向上”收敛为“受控向上”）。
- `yaml-dsl-workflow`: `runs[*].demand` 与 path aliases 的解析规则需要与 allow-roots 策略对齐（尤其是绝对路径与 alias base 的约束）。

## Impact

- 受影响代码路径：
  - `src/scalim/dsl/by_yaml/config_parsing/imports.py`（imports path normalize + resolve）
  - `src/scalim/dsl/by_yaml/workflow.py`（`resolve_workflow_demand_path` 与 alias 路径解析）
  - workflow validate / workflow entrypoints（递归校验 demand YAML 时的路径解析必须一致）
- 行为变化（可能影响既有用法）：
  - 依赖“向上任意级别 `../`”或“workflow 直接引用绝对路径”的用法会默认 fail-fast；需要显式配置 allow roots/允许绝对路径以继续使用
- 安全收益：
  - 将 YAML 文件系统读边界从“隐式依赖运行环境目录结构”收敛为“显式声明的信任根目录集合”，显著降低目录穿越与 symlink 逃逸导致的配置泄露风险
