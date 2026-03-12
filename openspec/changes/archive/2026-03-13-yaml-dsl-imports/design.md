## Context

现状:
- Scalim 的 YAML DSL 已支持通过 YAML anchors/alias 在单文件内复用对象,但无法跨文件复用,导致多 demand 拆分后出现大量 `sources/relations/fields` 重复。
- YAML merge(`<<`) 在本项目中是已知 footgun: merge 会生成新对象并破坏 alias 身份,不适合作为“继承/复用”的核心方案(且难以稳定校验与解释)。
- 当前 YAML 解析/校验链路为: `yaml.safe_load` → schema/语义 validator → 解析为 `DemandConfig` → IR/Plan/Engine。

目标是引入一个跨文件复用能力,但不改变现有运行时执行语义,且保持:
- 可被 JSON Schema 表达(用于 editor/schema validate)
- 可被语义 validator 解释并给出可操作诊断
- fail-fast(循环、类型不匹配、歧义直接报错)

## Goals / Non-Goals

**Goals:**
- 提供 demand YAML 的跨文件 `import/include` 能力,用于复用 `sources/relations/(fields)` 片段。
- 合并规则确定且直觉: deep-merge + 本地覆盖;类型不匹配报错;list replace。
- import 展开后再执行 schema/语义校验,保证“最终配置”可校验且与运行一致。
- **V1 仅支持同级目录导入**: `imports.*` 仅允许同级文件名(见后文 Decision 4)。
- 运行时兼容 Python 3.6,不引入新强依赖。

**Non-Goals:**
- 不支持网络/远程 include(仅本地文件)。
- 不把 YAML merge(`<<`) 作为官方复用机制的一部分。
- 不提供删除/patch 语义(例如 `$delete`)或 list concat 语义。
- 不引入 `multi main_source` 或 workflow 编排(由其它 change 处理)。
- 不做跨进程/跨天缓存;import 仅影响配置编译期。
- **V1 不支持跨目录/alias 路径**: 不支持绝对路径、`../`、子目录路径、`@/`、`ALIAS:/` 等路径形式。

## Decisions

1) **语法入口**
- 顶层新增 `imports: {<alias>: <path>}`。
- 在任意 mapping 节点内允许特殊键 `$import`:
  - `$import: common.sources`
  - `$import: [common.sources, other.sources]`

2) **引用解析规则**
- `$import` 引用字符串格式: `<alias>(.<segment>)*`。
- `<alias>` 必须存在于 `imports`。
- `<segment>` 必须为标识符字符串(正则: `^[a-zA-Z_][a-zA-Z0-9_]*$`),并按 `.` 分割逐段下钻。
- 导入文件解析结果与点路径下钻的目标值 MUST 为 mapping;否则报错。
- 允许片段文件自身包含 `imports/$import`,并递归展开后再参与合并。

3) **确定性合并规则**
- 合并顺序:
  1. 先按 `$import` 列表顺序合并所有导入片段(后者覆盖前者)
  2. 再与本地 mapping(剔除 `$import` 键)合并,本地覆盖导入结果
- deep-merge:
  - mapping vs mapping: 递归合并
  - list: 只允许 replace(本地覆盖导入)
  - scalar: 本地覆盖导入
  - 类型不匹配(例如 mapping vs scalar): 直接报错,避免隐式覆盖导致静默错误

4) **V1 路径解析(仅同级文件导入)**
- `imports.<alias>` 的 value 仅允许:
  - `common.yaml` / `common.yml`
  - `./common.yaml` / `./common.yml`
- 禁止:
  - 绝对路径(例如 `/a/b.yaml`, `C:\\a\\b.yaml`)
  - 父目录/子目录(例如 `../x.yaml`, `fragments/x.yaml`)
  - alias 前缀(例如 `@/x.yaml`, `COMMON:/x.yaml`)
- 解析 base_dir:
  - 对 `load(yaml_path)` / `run(yaml_path)` / `compile(yaml_path)` 等“文件路径入口”,base_dir 为该 YAML 文件所在目录。
  - 对片段文件递归展开时,base_dir 为片段文件所在目录(从而保证“同级”规则对每个文件自洽)。
- 约束动机:
  - V1 优先把合并语义、循环检测、诊断链路打稳;路径能力后续再扩展,避免把“路径策略”与“合并语义”绑死在同一个变更里。

5) **展开时机**
- import 展开必须发生在 schema/语义 validator 之前,且 validator/解析器只看到展开后的最终配置。
- **仅文件路径入口支持 import**:
  - `YamlDemandLoader.load(yaml_path)` 与 `scalim.dsl.by_yaml.run/compile(yaml_path)` 支持 import 展开。
  - CLI 校验命令(`scalim yaml-dsl validate` / `scalim yaml-dsl schema validate`)在读取到文件路径时,也必须先展开再校验,保证与运行入口一致。
  - `YamlDemandLoader.load_string(...)` 与纯文本校验(`validate_yaml_text`)因缺少 base_dir,若检测到 `imports` 或 `$import` MUST fail-fast 并提示改用文件路径入口。
- 错误信息必须包含 import 链路(文件路径 + 引用路径),以便定位到真实来源。
- 最大展开深度为 **20**;超过上限 MUST 报错并输出链路(避免病态递归/栈溢出)。

6) **文档/生成边界与 drift gate**
- Schema 变更通过 `schema_dsl` 元数据生成,并由 `tests/test_yaml_schema_generation.py` 漂移门禁兜底。
- 文档若涉及 `.gen.` 或 injected blocks,必须修改 SSOT 并运行 `just gen-docs`(不手改生成物)。
- OpenSpec 变更归档前运行 `just openspec-check` 保证规范可校验。

## Risks / Trade-offs

- [错误定位从“单文件行列号”变复杂] → MVP 保证错误包含导入链路与逻辑路径;后续可增强为带行列号的跨文件定位。
- [deep-merge 可能掩盖重复定义] → 类型不匹配直接报错;可选在诊断中输出冲突 key 列表(但默认不引入兼容/宽松模式)。
- [`$import`/`imports` 与业务字段命名冲突] → 使用 `$` 前缀保留字;并在 schema/validator 中显式声明其语义。
- [用户确实想传入 key 名为 `$import` 的 kwargs] → 明确 `$import` 为保留字: 任何 mapping 中出现 `$import` 都会触发 import 语义;不提供“转义/兼容模式”(避免歧义)。
- [读本地文件的安全边界] → include 仅在调用方触发(`run/compile`),默认视为受信环境;不引入远程协议或隐式下载。

## Future options (not in V1)

- 路径策略扩展:
  - 允许子目录(例如 `fragments/common.yaml`)
  - 允许 `../` 或 workspace root 限制(白名单目录)
  - 允许 `path_aliases` 注入(例如 `@/`、`COMMON:/`)
- 引用格式扩展:
  - 为 `<segment>` 引入转义(支持 `.` 出现在 key 中)
  - 允许 `$import` 引用“整文件默认导出”(不写点路径)
