## Context

下游旧工程通过 `scripts/vendor-sync.py` 将 `src/scalim/` 镜像到其 `vendors/libs/scalim/` 导入链路后直接运行，运行环境常见约束为：

- Python 3.6（无法升级）
- 无法/不允许在目标环境中 `pip install` 安装依赖

当前 `scalim` 的 YAML 解析逻辑在多处通过 `require_optional_dependency("yaml")` 动态引入 `PyYAML`，这在“只同步源码、不装依赖”的链路上会直接失败。

仓库已在 `src/scalim/vendor/yamlx/` 内 vendors 化了 `yaml`(PyYAML) 与 `ruamel.yaml` 两套实现，但直接以 `scalim.vendor.yamlx.*` 路径导入时存在“隐式依赖外部安装包”的问题：

- `PyYAML` 的 `cyaml.py` 存在 `from yaml._yaml import ...` 的绝对导入，可能意外指向系统 `site-packages/yaml`，或在下游无依赖时失败。
- `ruamel.yaml` 内部大量使用 `ruamel.yaml.*` 的绝对导入；在下游无依赖时会失败，在开发环境有依赖时会发生 vendors/系统混用。

## Goals / Non-Goals

**Goals:**

- `src/scalim/vendor/yamlx/` 内的 `yaml` 与 `ruamel.yaml` 在无外部依赖安装时可被导入使用（Python 3.6 兼容）。
- `src/scalim/` 内所有 YAML 解析入口不再依赖 `require_optional_dependency("yaml")`，统一改为使用 vendors 化的 `yamlx.yaml`。
- 在 Python 3.6 环境下对 `PyYAML` 与 `ruamel.yaml` 给出可操作的对比结论，为后续是否切换默认实现提供依据。

**Non-Goals:**

- 本次不承诺将 `scalim` 的 YAML 解析从 `PyYAML` 语义整体迁移到 `ruamel.yaml`（两者 API/语义差异较大，需单独评估与迁移计划）。
- 不引入新的外部运行时依赖（下游无法安装依赖是核心约束）。

## Decisions

### Decision: 以“最小侵入”方式修复 vendors 化包的导入边界

- 对 vendors 化的 `PyYAML`：
  - 将 `src/scalim/vendor/yamlx/yaml/cyaml.py` 中对 `yaml._yaml` 的绝对导入改为相对导入，确保不会意外落到系统 `site-packages/yaml`，并在无 C 扩展/不同 Python 版本时自然回退到 pure-python。
- 对 vendors 化的 `ruamel.yaml`：
  - 在 `src/scalim/vendor/yamlx/ruamel/yaml/__init__.py` 中增加导入期的 “module alias bootstrap”，将当前 vendors 化包注册为 `ruamel`/`ruamel.yaml`，从而让内部 `ruamel.yaml.*` 的绝对导入稳定解析到 vendors 化源码，而不是系统安装包。
  - 尝试将 `src/scalim/vendor/yamlx/_ruamel_yaml*.so` 作为可选 C 扩展暴露为顶层 `_ruamel_yaml`（仅当当前解释器能加载时启用；否则自动 pure-python 回退）。

该策略的优点：
- 改动集中且易审计（避免对 `ruamel.yaml` 全量做“绝对导入→相对导入”的大规模重写）。
- 在 Python 3.6 环境中可利用已 vendors 化的二进制扩展（若 ABI/平台匹配），否则自动回退。

代价/约束：
- `ruamel.yaml` 的 alias bootstrap 会写入 `sys.modules["ruamel"]`/`sys.modules["ruamel.yaml"]`（属于“邪恶但可控”的 vendors 化手段）。为了降低副作用，仅在显式导入 vendors 化 `scalim.vendor.yamlx.ruamel.yaml` 时发生。

### Decision: `scalim` 内 YAML 统一入口使用 `yamlx.yaml`

在 `src/scalim/` 内将所有 `yaml` 导入替换为 `from ...vendor.yamlx import yaml`（即 `yamlx.yaml`），并移除对应 `require_optional_dependency("yaml")` 的分支逻辑。

这样 vendors 同步后的 `scalim` 在下游无需安装 `PyYAML` 即可运行。

## Risks / Trade-offs

- [sys.modules alias 的副作用] 在同一进程内如果用户同时依赖系统 `ruamel.yaml`，导入 vendors 化版本可能导致模块名冲突 → 缓解：默认业务路径不导入 vendors 化 `ruamel.yaml`；仅在需要对比/实验时显式使用。
- [二进制扩展不可移植] vendors 化的 `.so` 可能在不同 Linux 发行版/架构/解释器编译选项下不可加载 → 缓解：所有 C 扩展都必须是可选项；导入失败自动回退 pure-python，不影响功能正确性。
- [行为差异风险] `ruamel.yaml` 与 `PyYAML` 在 round-trip、类型构造、标量解析等存在差异 → 缓解：本次默认继续使用 `PyYAML` 语义；对比结论仅用于后续决策。

## Migration Plan

- 将 `src/scalim/` 内 YAML 导入切换到 `yamlx.yaml` 后：
  - 对下游 vendors 使用者：仅需同步最新 `src/scalim/`，无需额外安装依赖。
  - 对常规 pip 安装使用者：行为不变（仍使用 `PyYAML` 语义），只是来源从系统包切换为内置 vendors。

## Open Questions

- 是否需要在文档中明确声明：当在同一进程内同时使用系统 `ruamel.yaml` 时，建议不要导入 vendors 化 `scalim.vendor.yamlx.ruamel.yaml`？
- 是否需要在 CI 中增加“模拟下游无依赖环境”的导入测试（例如通过隔离 `site-packages` 或运行最小化环境）？

## Py3.6 Evaluation (ruamel.yaml vs PyYAML)

实验环境（2026-03-30）：
- Python: `/home/l8ng/Downloads/tmp/a/.venv` → Python 3.6.15
- PyYAML: 6.0.1（`__with_libyaml__ = True`）
- ruamel.yaml: 0.18.3（`__with_libyaml__ = True`）
- 基准 YAML: `tests/fixtures/order_report.yaml`（约 4KB）

粗测结果（越低越快）：
- `yaml.safe_load`：约 8.4 ms/op（默认 `SafeLoader`，偏慢）
- `yaml.load(..., Loader=yaml.CSafeLoader)`：约 0.76 ms/op（显著更快）
- `ruamel.yaml.YAML(typ="safe").load`：约 1.63 ms/op
- `yaml.safe_dump`：约 4.3 ms/op（默认 `SafeDumper`）
- `yaml.dump(..., Dumper=yaml.CSafeDumper)`：约 0.67 ms/op（显著更快）
- `ruamel.yaml.YAML(typ="safe").dump`：约 2.28 ms/op
- `ruamel.yaml.YAML(typ="rt").load`：约 22.3 ms/op（round-trip 能力换来显著开销）

结论（面向本次变更）：
- 若继续维持 `PyYAML` 语义，使用 vendors 化 `yamlx.yaml` 最小改动即可满足下游约束。
- 性能层面：`PyYAML` 默认 `safe_load/safe_dump` 并不会自动使用 C Loader/Dumper；若后续需要性能优化，可考虑在 `scalim` 内部封装“优先使用 `CSafeLoader/CSafeDumper`”的统一入口（可选增强，不作为本次强制目标）。
