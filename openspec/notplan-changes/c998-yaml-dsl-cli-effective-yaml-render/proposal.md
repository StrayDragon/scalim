## Why

在真实集成中,下游经常需要把“作者写的 demand YAML”展开成一份可直接审阅/对拍/调试的 **effective YAML**(单文件等价配置),典型原因包括:

- demand 使用了 `imports/$import` 复用片段,review 时很难直观看到合并后的最终配置
- demand 使用了 `template_vars`(LiteJinja2 预编译)作为高级 workaround(例如动态生成一段 YAML 列表/字段集合),需要在运行前确认渲染结果
- 上述复用/模板在编辑器里会降低 YAML LSP/schema 的即时校验体验(模板语法对 LSP 不友好),下游希望能生成一份“展开后无模板语法”的 YAML 供排错与对照

当前仓库已提供库侧 API(`load_effective_demand_yaml` / `dump_effective_demand_yaml`)用于渲染 effective YAML,但 CLI 侧仍缺少一个稳定入口,导致:

- 下游必须写一段 Python glue 才能做预览/对拍,不利于脚本化与 CI/运维使用
- 团队内很容易出现各自实现的“渲染脚本”,产生双轨维护与行为漂移风险

### 复现/现状痛点(最小路径)

1) 编写包含 `imports/$import`(以及可选 `template_vars` 模板语法)的 demand YAML  
2) 需要查看“展开后的最终 YAML”用于 review/debug/对拍  
3) 目前 `scalim-cli yaml-dsl` 仅提供 `validate/schema/...` 等命令,缺少一个“render effective yaml”的命令  
4) 只能改为写 Python 脚本调用库侧 API 或走内部工具路径,对下游来说不够直观/不够标准化

## What Changes

- 新增一个 `scalim-cli yaml-dsl` 子命令,用于将 demand YAML 渲染为 effective YAML(展开 `template_vars` + `imports/$import`)并输出到 stdout 或文件,作为 review/debug/对拍的标准入口。
- 该命令支持调用方提供 `template_vars` 映射(dict),并要求其为 JSON/YAML-like 值(标量/列表/字典),以满足 `{% for ... %}` 等模板场景对 list/string 的传参需求。
- 该命令只做“展开”,不强制绑定 schema/semantic 校验流程(校验仍由 `yaml-dsl validate` 承担);但在展开失败时必须 fail-fast 并输出可诊断错误(包含导入 trace/逻辑路径等关键信息)。
- 安全边界: 若该命令暴露 `template_sandbox` 相关能力,默认 MUST 为安全模式,任何放宽行为 MUST 以显式 `unsafe` 语义暴露(避免把不安全能力挂到默认路径)。

## Capabilities

### New Capabilities
- `yaml-dsl-cli-effective-yaml-render`: 提供 CLI 入口渲染 effective YAML,用于 review/debug/对拍与脚本化消费。

### Modified Capabilities
- `yaml-dsl-cli-validation`: 扩展 `PROJECT_CLI_NAME yaml-dsl` 命令面,加入 effective YAML 渲染子命令,并纳入 CLI 回归测试与输出格式治理。

## Impact

- 受影响代码主要集中在:
  - `src/scalim/cli/yaml_dsl.py`(新增子命令与参数解析)
  - `src/scalim/dsl/by_yaml/config_parsing/effective_yaml.py`(复用既有 loads/dumps 能力;不改变其语义)
  - tests(新增 CLI 回归用例,覆盖渲染成功/失败诊断/输出稳定性)
  - docs(若新增用户可见文档/示例,需遵守生成物与注入区块治理规则;必要时运行 `just gen-docs`)

