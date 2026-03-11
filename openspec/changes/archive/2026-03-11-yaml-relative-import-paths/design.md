## Context

YAML DSL 中存在多处“Python 引用字符串”入口:

- `main_source.loader` / `sources.*.loader`
- `fields.*.call_by` 的 `reference(args...)` 中的 `reference`
- `*.retry.should_retry`

当前实现仅接受绝对 module path 的 dotted/class-style 引用,并依赖 allowlist(`allowed_modules`/`allowed_functions`)与安全 resolver 约束导入范围。
本变更希望在不削弱安全边界的前提下,增加 Python 风格相对模块引用语法 `.` / `..`,其基准为 YAML 文件所在目录。

约束:
- 运行时代码需保持 Python 3.6 兼容(不使用 3.7+ only 语法)。
- allowlist 仍为强约束;相对引用必须先被归一化为绝对引用再进入 allowlist/security 检查。

## Goals / Non-Goals

**Goals:**
- 允许在 YAML DSL 的 Python 引用字符串中使用相对 module path 前缀 `.` / `..`。
- 相对引用的基准明确为 YAML 文件所在目录(通过 `yaml_path` 计算“当前 module 路径”)。
- 对所有引用入口保持一致行为: loader / `call_by` / `should_retry`。
- 保持 allowlist/security 行为不变,并提供可操作的错误信息。

**Non-Goals:**
- 不引入新的 YAML 字段来声明 allowlist 或显式 module root。
- 不改变现有绝对引用解析与 allowlist 匹配策略(仅扩展语法)。
- 不在本变更中实现“跨项目/多根”自动推断规则(例如基于外部配置文件推断 package root)。

## Decisions

### Decision 1: 在 resolver 层做相对引用归一化

**Choice:** 将相对引用归一化逻辑放入引用 resolver,在 allowlist 与 security check 之前执行。

**Why:**
- 所有引用入口最终都会走 resolver;集中处理可避免 loader/call_by/retry 各自实现一套归一化逻辑。
- 归一化后的绝对引用可直接复用现有 allowlist 与 security check,避免出现“相对语法绕过校验”的风险。

**Alternatives considered:**
- 在 config parsing 阶段归一化: 但 config parsing 不总是有 `yaml_path`,且会把“运行时环境相关”(sys.path)的决策提前到纯解析阶段,边界不清。
- 在每个引用 callsite 单独归一化: 实现分散且容易漏掉新的入口。

### Decision 2: “当前 module 路径”由 `yaml_path` + `sys.path` 推导

**Choice:** 在 `compile/run` 入口(已具备 `yaml_path`)根据 `Path(yaml_path).parent` 推导 base module:
- 遍历 `sys.path` 条目,找出作为 `yaml_dir` 前缀的候选路径
- 选择“最长匹配”(最具体)的候选
- 将 `yaml_dir` 相对该候选路径的各级目录段用 `.` 拼接为 module path
- 目录段必须是合法 identifier;否则视为无法推导 base module

**Why:**
- 不引入新的配置面(保持调用侧 API 不变),且与 Python import 运行时事实(`sys.path`)一致。
- 最长匹配可减少多工作区/多路径注入时的歧义。

**Alternatives considered:**
- 依赖 `__init__.py` 扫描包边界: 对 namespace package/资源目录不稳健,且对用户目录结构约束更强。
- 仅基于 allowlist 推断 base: allowlist 描述“允许导入哪些模块”,不等价于 YAML 所在模块位置,容易误判。

### Decision 3: 语法与归一化规则

**规则:**
- 仅允许在 module path 位置使用 `.` / `..` 前缀(与 Python relative import 一致)。
- 前缀点数 `n` 的语义:
  - `n == 1`: 相对当前 module
  - `n > 1`: 向上回退 `n-1` 层 module path
  - 超出根层级则报错
- 归一化输出必须是既有绝对引用格式,再进入现有 allowlist/security 检查。

## Risks / Trade-offs

- [无法推导 base module] → 相对引用在某些 YAML 放置位置会 fail-fast;缓解: 错误信息提示改用绝对引用或调整 YAML 放置位置/`PYTHONPATH`。
- [多 `sys.path` 前缀歧义] → 选择“最长匹配”并在错误信息中输出推导结果(便于定位)。
- [用户误以为相对引用不受 allowlist] → schema/skill 文档必须明确“归一化后仍受 allowlist 约束”,并给出如何调整 allowlist 的提示。

## Migration Plan

- 本变更为向后兼容的语法扩展:
  - 现有绝对引用不受影响
  - 使用相对引用的 YAML 在旧版本将被校验拒绝;升级后可通过
- 回滚策略: 回滚到旧版本时,需要把相对引用改回绝对引用。

## Open Questions

- 对于 `YamlDemandLoader.load_string(...)` + `ConfigToIRConverter(...)` 这类无 `yaml_path` 的调用链:
  - 是否需要新增显式参数(例如 `base_module` / `yaml_dir`)以支持相对引用,或仅在遇到相对引用时给出“需要 yaml_path/base_module”的错误提示。
