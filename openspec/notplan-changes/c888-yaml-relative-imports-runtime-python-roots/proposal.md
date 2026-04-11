## Why

当前 YAML DSL 支持在 `loader` / `call_by` 中写相对引用（以 `.` / `..` 开头），例如：

- `loader: ".loaders:load_orders"`
- `call_by: "..common.transforms:fixup(status)"`

相对引用要能工作，运行期必须先推导出 `base_module_path`，把相对模块引用归一化为 “可 `import` 的绝对模块名”。
现有推导规则依赖 `yaml_path` + `sys.path`：

- 若 “YAML 所在目录” 不在任何 `sys.path` 条目之下，会 fail-fast 报错（这在下游只注入 allowlist、但未显式设置 `PYTHONPATH` 的场景里非常常见）。

这对用户直觉不友好：

- 用户看到的是 “相对引用”，直觉上会认为它只跟 YAML 文件位置有关；
- 但实际还依赖运行时的 `PYTHONPATH`/`sys.path` 引导（尤其是脚本/批处理入口，容易漏配或在不同启动方式下漂移）。

本问题在 ET 一类“批处理/多入口/多 `PYTHONPATH` 组合”中会被放大：同一份 YAML 在不同启动脚本下被归一化成不同的绝对模块名，进而影响 allowlist 行为与可移植性。

为便于讨论，本仓库已提供一个不改框架机制的最小复现：

- `notebooks/marimo/example_yaml_relative_imports_mvp/`

## What Changes（提案）

新增一个 **显式、可审计** 的运行期能力：允许调用方在 `run/compile/run_workflow` 入口处提供 “Python 导入根目录列表”，由框架在编译阶段临时注入到 `sys.path`，从而让相对引用可推导、可导入。

建议形态（示意）：

- 在 `RunOptions` 增加 `python_roots: tuple[str, ...] | None`
  - 仅影响编译期（推导 `base_module_path` + 运行时绑定解析）
  - 必须校验为“存在的目录”
  - 必须是临时注入，保证编译结束后 `sys.path` 恢复
  - **不改变** allowlist 语义：仍然需要 `allowed_modules/allowed_functions` 明确放行

并同步优化错误提示：当无法从 `sys.path` 推导 `base_module_path` 时，除提示 `PYTHONPATH` 外，也提示“可通过 `RunOptions(python_roots=...)` 解决”。

## Non-goals（本提案不做）

- 不做 “自动向上猜包根目录并修改 `sys.path`” 的隐式行为（歧义大、可解释性差、也会放大安全与可维护性风险）。
- 不把 LSP 的 `python_roots` 直接复用为运行期导入根（避免把编辑器配置与运行期语义绑定在一起，造成不可控漂移）。
- 不放宽任何安全边界（例如不引入 wildcard allowlist 的默认放开）。

## Design Sketch

运行期关键点在于：把 “导入根注入” 限定在编译期，并保证可回收。

```
run/compile(...)
  ├─ validate_allowlist(...)
  ├─ with patch_sys_path(python_roots):
  │    ├─ load_config(yaml)
  │    ├─ derive_base_module_path(yaml, sys.path)
  │    ├─ resolve_runtime_bindings(...)  # 这里会 import loader/call_by
  │    └─ build_request(...)
  └─ 执行阶段只消费 RuntimeBindings（不再 import）
```

补充：对 `workflow`，原则上应在“每个 demand 的编译节点”复用同一份注入策略（或允许 per-run 覆盖）。

## Impact

- 对下游的影响（预期）：
  - 可把“必须显式配置 `PYTHONPATH`”降级为“可选”：入口只要传 `python_roots` 即可稳定运行相对引用。
  - allowlist 仍然是必需的安全边界，不会因为新增 `python_roots` 而被绕过。
- 对框架的影响（预期）：
  - 代码改动集中在 YAML DSL 的编译入口与 `workflow` demand 编译入口。
  - 行为变更是“新增能力”，不改变默认 fail-fast 行为（未传 `python_roots` 仍按现有规则报错）。

## Open Questions

- `python_roots` 的命名与边界：是否需要区分 `python_roots`（仅推导 base module）与 `extra_sys_path`（仅用于 import）？
- `workflow` 的注入策略：是否允许 per-run 节点覆盖，还是只允许 workflow 级统一配置？

