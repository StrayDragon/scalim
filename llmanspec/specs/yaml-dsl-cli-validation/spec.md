---
llman_spec_valid_scope:
  - src/scalim/
llman_spec_valid_commands:
  - llman sdd validate yaml-dsl-cli-validation --type spec --strict --no-interactive
llman_spec_evidence:
  - migrated from openspec
---

```toon
kind: llman.sdd.spec
name: "yaml-dsl-cli-validation"
purpose: "定义 CLI 校验工具的行为契约，包括校验分层、诊断输出格式与错误定位，确保 CLI 结果可用于 IDE 跳转、CI 报告与脚本化消费。"
requirements[13]{req_id,title,statement}:
  r1,CLI 与 runtime core 职责分离,"系统 MUST 允许 CLI 实现独立于 runtime core 发行，但 MUST 保持对外行为契约一致： - 校验逻辑 MUST 委托 runtime core 的可复用服务层，不得在 CLI 中复制语义实现 - runtime core MUST 可在不安装 CLI 的环境中被 import 使用 - CLI 的退出码、JSON payload 结构、诊断输出格式 MUST 保持规范一致"
  r2,校验契约 SSOT,"系统 MUST 将 YAML DSL 的输入契约规则集中为单一实现： - workflow compile、runtime compile、CLI validate MUST 复用同一套校验规则 - 对同一非法输入，不同入口 MUST 给出一致的接受/拒绝结果 - 错误信息 MUST 包含一致的关键字段（逻辑 path、失败原因、修复建议）"
  r3,CLI validate 职责边界,"系统 SHALL 明确区分 validate 与 schema validate： - `validate` 使用内部语义校验器，输出可行动诊断 - `validate` MUST NOT 执行 JSONSchema 校验，MUST NOT 输出 schema 依赖相关 warning - `schema validate` 作为 schema-only 校验入口，依赖 `jsonschema` 并在缺失时 fail-fast - 系统 MUST 对同一未知字段避免重复诊断（unknown-fields 与 additionalProperties 重叠时去重）"
  r4,"校验覆盖 fail-late 情况","系统 MUST 确保 validate 与 schema validate 对已知 fail-late 形态给出一致失败结果： - 非法 mapping key（空 key/不匹配 identifier pattern） - 空 loader/key 字段 - retry enabled 但缺失 should_retry - 非法 streaming/fields 配置"
  r5,JSON 输出格式,"系统 SHALL 在 `--json` 模式下输出结构化 JSON，包含 `ok`、`errors`、`yaml_path` 字段。"
  r6,源码位置定位,"系统 SHALL 在诊断输出中提供可跳转位置，格式至少包含 `path:line`。 - 当无法解析具体位置时，MUST 退化为文件级位置 - `ValidationIssue.path` MUST 使用 canonical 点号口径，支持 bracket 索引归一化"
  r7,Linter 风格输出,系统 SHALL 将非 JSON 输出统一为 linter/编译器风格，以单条诊断块展示级别、消息与位置，verbose 模式下附带源码片段。
  r8,Schema 发现与查看,系统 SHALL 提供 schema show 与 schema path 命令，用于查看当前 JSON Schema 及其路径。
  r9,LSP comment 管理,"系统 SHALL 提供 upsert-lsp-comment 命令，用于在 YAML 文件中插入或更新 schema modeline： - 支持 Red Hat YAML Language Server 与 IntelliJ 两种格式 - 支持 `--comment-style` 控制写入风格 - 命令 MUST 幂等，未变更时不改写文件"
  r10,Lint 命令,"系统 MUST 提供 lint 命令，用于 YAML DSL authoring 风格与易踩坑点静态检查： - 支持文件与目录输入，递归发现 YAML 文件 - 输出可跳转位置与稳定规则 code - 支持 `--json` 与 `--fix`（仅执行确定性安全修复） - v1 规则覆盖：quoted reference 可去引号、plain scalar 类型歧义、长 call_by 建议"
  r11,Format 命令,"系统 MUST 提供 format 命令，用于 YAML DSL 幂等格式化： - 支持文件与目录输入 - format MUST 幂等（重复运行产生 0 diff） - 聚焦特定字段的 string value 风格归一 - 仅当 plain scalar 仍会被解析为同一 string 时才去引号 - 支持 `--check` 与 `--diff`"
  r12,"demand `schema validate` MUST support `--workflow` context for outputs→resources","系统 MUST 允许用户在对 **demand YAML** 执行 `yaml-dsl schema validate` 时提供 workflow 上下文参数： - `yaml-dsl schema validate --workflow <workflow.yaml> <demand.yaml>` 当提供 `--workflow` 时，系统 MUST： - 读取并解析 `<workflow.yaml>`，并提取可见资源 id 集合： - visible books = demand `resources.books` ∪ workflow `workflow.resources.books` - visible files = demand `resources.files` ∪ workflow `workflow.resources.files` - 在 schema-only 校验的 outputs 绑定检查阶段，对每个 output 的 destination 执行资源存在性校验： - 若 output 绑定到 `to.book=<book_id>`：`<book_id>` MUST 存在于 visible books - 若 output 绑定到 `to.file=<file_id>`：`<file_id>` MUST 存在于 visible files - 当 `<workflow.yaml>` 无法读取/解析时，schema validate MUST fail-fast（不得静默忽略 workflow 上下文）。"
  r13,"demand `validate` MUST support the same `--workflow` context behavior as `schema","系统 MUST 允许用户在对 **demand YAML** 执行 `yaml-dsl validate` 时提供 workflow 上下文参数： - `yaml-dsl validate --workflow <workflow.yaml> <demand.yaml>` 并且该上下文的资源可见性语义 MUST 与 `schema validate` 一致（同一份输入在同一 workflow 上下文下，两者对 outputs→resources 绑定的接受/拒绝结果 MUST 一致）。"
scenarios[38]{req_id,id,given,when,then}:
  r1,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r1,"runtime-可独立使用",环境未安装 CLI 发行物,调用方导入并使用 runtime 入口,导入与运行 MUST 成功
  r1,"cli-复用统一校验逻辑","",YAML 在 runtime compile 中失败,CLI validate MUST 以相同结构失败
  r2,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r2,非法输入在各入口一致失败,用户提供非法配置（如非法 sheet_name/输出名）,通过不同入口校验,"各入口 MUST 均 fail-fast 且给出一致诊断"
  r3,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r3,"validate-不依赖-jsonschema",运行环境未安装 jsonschema,用户运行 validate 命令,命令应正常执行且不输出 schema 依赖 warning
  r3,"schema-validate-收集完整错误",YAML 配置触发多条 schema 错误,用户运行 schema validate,输出 MUST 包含全部错误且排序稳定
  r3,未知字段诊断不重复,"",配置包含未知字段,"错误列表 MUST 包含 unknown-fields 诊断"
  r4,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r4,"fail-late-情况早期捕获",YAML 包含上述任一错误形态,用户执行 validate,命令 MUST 失败且错误指向对应路径
  r5,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r5,"json-输出结构","","使用 `--json` 校验配置",输出可解析的 JSON 且包含必需字段
  r6,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r6,错误包含源码位置,"",校验失败,"输出应包含 `path:line[:column]` 位置"
  r6,"bracket-path-归一化","validator 产出 `outputs[0].path`",CLI 输出诊断,MUST 能定位到对应源码位置
  r7,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r7,"使用-linter-风格输出","",用户以默认方式运行校验,"每条诊断按 `ERROR ... --> path:line` 形式输出"
  r8,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r8,"schema-查看","",用户执行 schema show,输出可解析的 JSON Schema
  r8,"schema-路径查看","",用户执行 schema path,输出 schema 的绝对路径
  r9,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r9,"插入两种-header",YAML 文件头部不包含 schema modeline,"用户使用 `--comment-style all`",文件头依次插入两种 modeline
  r9,"仅保留特定-header",文件包含两种 modeline,"用户指定单一 comment-style",仅保留对应格式的 modeline
  r10,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r10,"fix-移除不必要引号","YAML 包含 `compute: \"order_id\"`","用户执行 lint --fix","修复为 `compute: order_id` 且仍可解析为 string"
  r10,"json-输出结构化","","用户执行 lint --json",输出 JSON 包含 issue 的 code 与 range
  r11,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r11,"format-幂等且安全","YAML 包含 `loader: \"pkg.mod:load_orders\"`",用户执行 format,"输出 `loader: pkg.mod:load_orders`"
  r11,"format-保留必要引号","YAML 包含 `should_retry: \"false\"`",用户执行 format,保留引号以确保值仍为 string
  r12,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r12,"schema-validate-accepts-a-workflow-declared-book-id",workflow YAML 声明 `workflow.resources.books.report`,"调用方执行 `yaml-dsl schema validate --workflow workflow.yaml demand.yaml`",校验 MUST 通过（退出码为 0）
  r12,"schema-validate-accepts-a-workflow-declared-file-id",workflow YAML 声明 `workflow.resources.files.detail_csv`,"调用方执行 `yaml-dsl schema validate --workflow workflow.yaml demand.yaml`",校验 MUST 通过（退出码为 0）
  r12,"schema-validate-fails-fast-when-workflow-context-cannot-be-l","用户提供不存在的 `--workflow missing.yaml`","调用方执行 `yaml-dsl schema validate --workflow missing.yaml demand.yaml`","命令 MUST fail-fast（非零退出码）"
  r12,"schema-validate-still-rejects-unknown-ids-even-with-workflow",workflow YAML 未声明 `workflow.resources.books.report`,"调用方执行 `yaml-dsl schema validate --workflow workflow.yaml demand.yaml`","命令 MUST fail-fast（非零退出码）"
  r13,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r13,"validate-accepts-a-workflow-declared-resource-id",workflow YAML 声明 `workflow.resources.books.report`,"调用方执行 `yaml-dsl validate --workflow workflow.yaml demand.yaml`",校验 MUST 通过（退出码为 0）
  r13,"validate-accepts-a-workflow-declared-file-id",workflow YAML 声明 `workflow.resources.files.detail_csv`,"调用方执行 `yaml-dsl validate --workflow workflow.yaml demand.yaml`",校验 MUST 通过（退出码为 0）
```
