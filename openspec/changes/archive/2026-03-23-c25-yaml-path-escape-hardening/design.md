## Context

by_yaml 存在多处“从路径读取 YAML”的入口（demand imports fragments、workflow runs demand、workflow path aliases）。当前实现的共同问题是：

1. 将 raw path 组合/`resolve()` 得到最终路径后，没有统一的“允许根目录（allow-roots）”约束；
2. 因此 `..` 与 symlink 可以把读取边界扩展到入口 YAML 目录之外，形成目录穿越/越界读取脚枪。

As-Is 代码路径（代表性）：

- imports v2：`src/scalim/dsl/by_yaml/config_parsing/imports.py`
  - `_normalize_import_path()` 允许 `../x.yaml`（仅禁止绝对/URI/保留 alias 前缀）
  - `_parse_imports_mapping()` 用 `(base_dir / normalized).resolve()` 得到最终路径，但缺少 allow-roots 校验
- workflow demand path：`src/scalim/dsl/by_yaml/workflow.py::resolve_workflow_demand_path()`
  - 允许相对路径、alias 路径、以及绝对路径（`Path(raw).is_absolute()` 直接放行）
  - 解析后 `resolve(strict=False)`，但缺少 allow-roots 校验

约束：

- `src/scalim/` 运行时需兼容 Python 3.6。
- 本变更属于安全 hardening，可引入 BREAKING（默认更安全），但必须提供明确的可用性补偿（显式 allow-roots）与可诊断错误信息。
- 对外入口需要覆盖 Python API（`scalim.dsl.by_yaml.*`）与 CLI validate（含 workflow validate 递归加载 demand 的路径解析）。

## Goals / Non-Goals

**Goals:**

- 为所有“将要读取的 YAML 路径”引入统一 allow-roots 策略：
  - 先 `resolve()` 得到 `resolved_path`
  - 再校验 `resolved_path` MUST 位于调用方声明的 `allowed_yaml_roots` 之一的目录树内
- 默认安全：当调用方未显式配置 allow-roots 时，默认 roots 至少包含入口 YAML 所在目录（从而默认阻断任意层级 `../` 逃逸）。
- 可用性不退化：需要跨目录复用配置的用户，可以通过显式传入额外 roots 达成（“受控向上/受控跨目录”）。
- 错误信息必须可诊断：raw path / base_dir / resolved path / allowed roots 一应俱全（便于快速定位误配置）。
- 默认阻断 symlink 逃逸：基于 `resolve()` 后的真实路径做 root 校验，避免 “root 内 symlink → root 外” 读越界。

**Non-Goals:**

- 不支持通过 imports/workflow 读取非本地文件（URI schemes）。
- 不在本变更中引入新的“虚拟文件系统”或 sandbox 依赖。
- 不改变 imports 语义（merge 覆盖/填充规则、$import 语法等）；仅收敛“路径可读取的边界”。

## Decisions

### 1) 定义统一的 allow-roots helper（单点实现，三处复用）

**决策：**

- 新增一个轻量 helper（建议位置：`src/scalim/dsl/by_yaml/config_parsing/allowed_paths.py` 或同级模块），提供：
  - roots 归一化：把 `allowed_yaml_roots` 转成绝对路径列表（`expanduser + resolve(strict=False)`）
  - 路径校验：对候选 `resolved_path` 做 `resolved_path.relative_to(root)` 检查（任一 root 命中即允许）
  - 统一错误构造：按规范输出 raw/base_dir/resolved/roots
- 将以下三处全部改为“解析 → resolve → allow-roots 校验”的流程（同一 helper）：
  - imports fragments（`imports.`*）
  - workflow runs demand（`runs[*].demand`）
  - workflow path aliases（alias base + rel 拼接结果）
- 该 helper 必须作为后续 imports aliases/presets（见 `yaml-dsl-import-aliases-and-presets`）的 roots 校验复用点，避免出现两套策略与错误格式漂移。

**备选：**

- 各模块自行实现 `relative_to` 校验：容易重复/漂移，并且错误消息难统一。
- 仅在字符串层禁止 `..`：仍然无法阻止 symlink 逃逸，且对 Windows/边界情况处理更脆弱。

### 2) 默认 roots：入口 YAML 所在目录（可显式扩展）

**决策：**

- demand imports：默认 `allowed_yaml_roots = {demand_yaml.parent}`。
- workflow：默认 `allowed_yaml_roots = {workflow_yaml.parent}`，并且递归加载被引用的 demand YAML 时复用同一 roots 集合（保证边界一致）。
- 需要跨目录（例如 `../_shared/common.yaml`）的用户，必须显式把对应“更上层”目录加入 roots（例如允许根为 repo root 或项目配置根）。

**理由：**

默认允许“同目录/子目录”复用是最符合直觉的安全边界；向上/跨目录属于显式信任扩展，应通过 roots 表达。

### 3) 绝对路径策略：允许表达，但仍必须在 roots 内

**决策：**

- workflow `runs[*].demand` 允许绝对路径表达，但最终 `resolved_path` 仍必须位于 allow-roots 内（否则 fail-fast）。
- imports v2 继续保持“仅相对路径”的 authoring 约束（`_normalize_import_path` 现有规则不变），但仍在 `resolve()` 后执行 roots 校验（阻止 `../` 与 symlink 逃逸）。

**理由：**

绝对路径本身不是安全问题（roots 才是边界）；保留绝对路径表达可减少“过度限制可信用户”的摩擦，同时用 roots 提供明确的信任边界。

### 4) 错误信息与排障体验：强制包含 raw/base/resolved/roots

**决策：**

- 所有拒绝都必须携带：
  - raw path（原字符串）
  - base_dir（解析基准）
  - resolved path（最终用于读取的路径）
  - allowed roots（归一化后的列表，便于比对）
- 对 workflow alias 场景，错误还应包含 alias 名称与 alias base（便于定位是 alias 配置问题还是 rel 问题）。

## Risks / Trade-offs

- [BREAKING] 现存依赖 `../` 或 workflow 引用其它目录 demand 的用法会默认失败 → 缓解：提供 `allowed_yaml_roots` 显式扩展入口；错误信息给出可复制修复提示。
- [误配置] roots 过大（例如直接允许 `/`）会削弱安全边界 → 缓解：对 roots 过大仅做 warning（不强拦截），并在文档中强调只在可信输入场景使用。
- [平台差异] `Path.resolve(strict=False)` 在不同 OS/文件存在性下行为略有差异 → 缓解：统一使用“先 resolve（尽可能解析 symlink）再 relative_to”策略；对不存在文件仍 fail-fast（读取阶段会报错），并确保错误消息稳定可诊断。

## Migration Plan

1. 引入 allow-roots helper 与策略对象（若需要），并为 imports/workflow 两条入口接入。
2. 为 Python API 与 CLI validate 增加 `allowed_yaml_roots`（或等价参数）注入能力，默认值为入口 YAML 所在目录。
3. 增加回归测试：
  - `imports: ../../secrets.yaml` 在默认 roots 下 fail-fast
  - 显式 roots 扩展后允许受控跨目录 imports
  - workflow `runs[*].demand` 的 `../`、绝对路径与 alias 路径在默认 roots 下 fail-fast（若越界）；在 roots 覆盖后允许
  - symlink 逃逸：root 内 symlink 指向 root 外文件必须 fail-fast
4. 运行 `just openspec-check` 与 `just qa` 作为最终门禁。

## Open Questions

- CLI 注入参数命名：`--allowed-yaml-root`（可重复）vs `--allowed-yaml-roots`（逗号分隔）。推荐可重复参数，便于 shell/CI 组合。

> - `--allowed-yaml-root`（可重复）



- roots 的“存在性校验”策略：是否要求 root 必须存在且为目录？（倾向要求存在，避免静默配置错误。）

> - 要求存在，避免静默配置错误
