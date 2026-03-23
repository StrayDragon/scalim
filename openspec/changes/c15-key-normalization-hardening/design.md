## Context

`key_normalization` 已作为实验性能力落地,并在规范中要求: 当启用非 `raw` 模式时,系统必须在一次运行内至少发出一次包含 `EXPERIMENTAL` 的提示,且文案包含当前启用的 `key_normalization` 值、不得包含明细 key 值、并应在一次运行内去重(避免刷屏)。

本变更要补齐一类“上线后才会遇到”的边界风险:

- **提示可见性**: 当前 `EXPERIMENTAL` 提示在默认配置下可能不可见(例如未挂载 observer/hook,也未显式开启 fallback logger)。
  - As-Is: `run_ir` 会调用 `InstrumentationHub.emit_diagnostic_warning(..., sample_once=True)` 发出提示,但在“无订阅 + fallback logger 未开启”的情况下会直接返回(无 stderr/log 输出): `src/scalim/execution/run_ir.py` / `src/scalim/ob/hub.py`。
- **loader/cached mapping 边界诊断**: loader 返回的 mapping key 口径与当前匹配口径交互复杂,在极端情况下容易踩坑(例如 key 口径不一致、cached mapping 规范化时发生 key collision)。需要补齐更可诊断的告警/错误上下文,同时保持“不泄露明细 key 值”的安全约束。
  - As-Is: cached/preload mapping 的 str-view collision 目前一律 fail-fast(无法在 values 相等时“安全合并继续”): `src/scalim/execution/executor/runtime/runtime.py`。

约束与工程规则:

- 运行时需兼容 Python 3.6。
- 文档治理: 不手改任何 `.gen.` 文件与 `BEGIN/END AUTOGEN:<id>` 区块;行为变更需同步 `openspec/specs/*/spec.md`;共享/发布前运行 `just openspec-check`。

## Goals / Non-Goals

**Goals:**

- 当 `key_normalization != "raw"` 时,在**默认配置**下也能在一次运行内明确看到一次包含 `EXPERIMENTAL` 的提示(一次去重)。
- 补齐 loader/cached mapping 相关的边界诊断:
  - 当 loader 返回的 mapping key 口径与当前匹配口径不一致时,提供可诊断的告警/错误(不泄露明细 key 值)。
  - 当 mapping 在构建规范化视图时发生 key collision 时,提供开箱即用的安全处理与明确诊断: values 相等则合并继续+告警,values 不相等则 fail-fast(均不泄露明细 key 值)。
- 明确文档/生成边界与 drift gate: 哪些属于 OpenSpec 规范、哪些属于代码实现与测试,以及如何防止规范与实现漂移。

**Non-Goals:**

- 不引入新的 `key_normalization` 模式;不改变既有规范化算法/匹配边界定义,仅在 collision 场景引入“值相等可安全合并”的处理以提升开箱即用。
- 不在任何告警/错误中输出 raw key 的明细值。
- 不依赖用户“必须额外挂载 observer/hook 或显式开启 fallback logger”才能看到实验性提示。

## Decisions

### 1) 默认可见的 EXPERIMENTAL 提示通道

为满足“默认配置可见”的硬要求,将 `EXPERIMENTAL` 提示至少通过一种**无需额外配置即可默认可见**的通道发出:

- 首选: 使用 Python `warnings.warn(...)` 发出项目内专用 warning 类 `ScalimExperimentalWarning`(继承 `UserWarning`)。
  - 原因: 默认 filter 下 warning 会输出到 stderr,满足“默认可见”;同时不绑定项目的 observer/hook 或 fallback logger。
  - 最佳实践:
    - 使用 `category=ScalimExperimentalWarning` 便于调用方按类过滤/升级为 error
    - 使用合适的 `stacklevel`(例如 2) 让 warning 指向更接近调用方的代码位置
    - 不修改全局 warnings filter,仅负责发出 warning

如系统已存在 observability hub/事件流,可在同一触发点额外发出结构化告警事件,但 **warnings 通道作为兜底** 以保证默认可见性。

### 2) 触发时机与一次运行去重

- 触发时机选择在“运行开始/运行上下文已确定 `key_normalization` 值”的位置,确保**一次运行只触发一次**。
- 去重策略:
  - 若已有 `sample_once`/运行内去重语义,复用其机制;
  - 否则在运行期上下文维护一个轻量的 `set`/flag(按告警类型 key 去重),保证 warnings 与事件两条通道也不会重复刷屏。

### 3) loader / cached mapping 的口径一致性诊断

补齐两类诊断,均遵循“不输出明细 key 值”的约束(仅输出 source/步骤名、key 类型信息、计数、模式等上下文):

- **mapping key 口径不一致**:
  - 当当前匹配口径要求进入字符串规范化 key space(例如 `force_str`,或 `auto_str` 且未显式 cast),但 loader 返回 mapping 的 key 呈现出明显不一致(例如非预期类型混入、或无法按当前策略构建可命中视图)时,给出可诊断的告警/错误。
  - 优先策略: 仅在“可以明确判断为不一致/高风险”时 fail-fast,否则先以告警提示并引导用户检查 loader 实现与 cast/key_normalization 的组合。
- **mapping 规范化 collision（包含 cached/preload）**:
  - 当对 mapping 构建规范化视图时发生 key collision,优先做“开箱即用”的安全处理:
    - 若 collision 的 value 全部 `==`(深度相等),则视为同一语义实体,保留任一值并继续(仍记录一次 redacted 诊断告警,便于用户清理数据/loader)
    - 若 collision 的 value 存在差异,则 fail-fast(避免 silent 选择导致隐性错误)
  - 错误/告警上下文需增强,包含: source/loader 标识、`key_normalization` 模式、collision 计数/比例(如可得)、以及下一步排查建议(仍不包含明细 key 值)。

为减少误报并覆盖真实场景,对 “mapping key 口径不一致” 采用“高置信度判定 + 具体建议”的策略:

- 高置信度 fail-fast:
  - 启用字符串规范化口径时,发现 mapping key 中存在无法被 `auto_str_normalize` 处理的 key(规范化失败)且会影响命中(例如 lookup 需要匹配到该 key)
  - 发生 collision 且 values 不一致(见上)
- 优先告警(不直接失败):
  - mapping keys 呈现明显混用类型(例如 `int`/`str` 混用),但 collision 均可安全合并或暂无法证明会导致错配
  - `auto_str` 且存在显式 cast: 发现 “cast 后候选 key 命中失败,但对候选 key 做字符串规范化后能够命中” → 强提示 loader 可能仍使用字符串口径,建议调整 cast 或 loader

推荐方法(面向用户/集成方):

- 当启用 `key_normalization` 的字符串模式时,优先保证 loader 返回 mapping 的 key 口径与“最终匹配口径”一致(例如统一为稳定字符串),避免混用导致 collision 或命中漂移。
- 若在 `auto_str` 下显式配置了 `lookup_cast`/`key.cast`,请确保 loader mapping key 口径与 cast 结果一致;否则更建议去掉显式 cast 或改用 `force_str`(以规范化为最终口径)。

### 4) 文档/生成边界与 drift gate

- 规范 SSOT: `openspec/specs/key-normalization/spec.md`(本变更的需求变更需最终落到该规范;changes 下的 specs 作为变更期间的增量输入)。
- 生成边界:
  - 不直接修改任何 `.gen.` 文件与注入块内容;
  - 若规范/文档 SSOT 发生变化,使用 `just gen-docs` 刷新生成产物与注入块。
- Drift gate:
  - 增补/更新测试用例,覆盖“默认配置下 EXPERIMENTAL 提示可见”与“collision/mismatch 诊断不泄露明细 key 值”的关键路径;
  - 在变更完成前运行 `just openspec-check` 与 `just qa`(或 CI 对应门禁)以防止规范/实现漂移。

## Risks / Trade-offs

- `warnings` 可能被调用方全局过滤或重定向: 该变更仅保证“默认配置”可见;若调用方主动屏蔽 warnings,可视为显式选择。
- 额外的诊断检查可能带来轻微开销: 仅在启用非 `raw` 模式时开启,并保持检查为 O(n) 且尽量在缓存/构建视图阶段执行。
- fail-fast 边界需要谨慎: 对“可明确判定会导致错配/误命中”的情况 fail-fast;对灰区先告警,避免引入不必要的破坏性变更。

## Migration Plan

1. 实现运行开始时的 `EXPERIMENTAL` 提示发出(默认可见 + 一次运行去重)。
2. 为该提示补齐单测/集成测,确保“无 observer/hook/未显式启用 fallback logger”仍可观测。
3. 增强 loader/cached mapping 的 mismatch/collision 诊断,并补齐覆盖关键场景的测试。
4. 同步/校验 OpenSpec 规范与变更 specs,运行 `just openspec-check`。
5. 通过 `just qa`/CI 质量门禁后再合并/发布。

## Resolved Questions

- warning 类: 引入项目内专用 `ScalimExperimentalWarning(UserWarning)`,通过 `warnings.warn(..., category=..., stacklevel=...)` 发出,不改全局 filter,默认可见且可被调用方精细过滤。
- mismatch 判定: 以“高置信度 fail-fast + 其余告警”为原则,通过真实场景用例(混用类型、显式 cast 与字符串口径交错、cached mapping)覆盖并沉淀推荐修复方法。
- collision 策略: 采用开箱即用的安全处理——collision values 全部相等则合并继续,否则 fail-fast;并增强 redacted 诊断信息指导排查。
