---
llman_spec_valid_scope:
  - src/scalim/
llman_spec_valid_commands:
  - llman sdd validate governance-package-identity --type spec --strict --no-interactive
llman_spec_evidence:
  - migrated from openspec
---

```toon
kind: llman.sdd.spec
name: "governance-package-identity"
purpose: "定义项目包身份与分发边界的治理规范，确保 PyPI 发行名、导入根包名、CLI 命令名之间的清晰分离，以及运行时主包与 CLI 发行物的版本约束解耦。"
requirements[5]{req_id,title,statement}:
  r1,PyPI 发行名为 PROJECT_DIST_NAME,系统 MUST 使用 `PROJECT_DIST_NAME` 作为唯一对外 PyPI 发行名(distribution name). 系统 MUST NOT 以 `PROJECT_DIST_NAME` 作为对外发布名.
  r2,顶层导入根包为 PROJECT_IMPORT_ROOT,系统 MUST 以 `PROJECT_DIST_NAME` 作为顶层导入根包名(root package). 系统 MUST NOT 在发行物中包含顶层包 `PROJECT_DIST_NAME`(不提供兼容层).
  r3,CLI 命令名为 PROJECT_CLI_NAME,"系统 MUST 提供 `PROJECT_CLI_NAME` 作为命令行入口,并保持其子命令树与现有 `PROJECT_CLI_NAME` 语义一致(仅命名变更). 补充约束（分发边界）： - `PROJECT_CLI_NAME` MUST 由独立 CLI 发行物提供（例如 `scalim-cli`），并允许该发行物使用更高的 Python 版本约束（例如 requires-python >=3.10）。 - runtime 主包 MUST 保持 Python 3.6 兼容且不承载 CLI 入口实现。"
  r4,使用 uv 标准 lib 结构与 uv_build 后端,"系统 MUST 采用 uv 标准 lib 结构进行分发: - 运行时包 MUST 位于 src/ 布局的标准目录（uv init --lib 生成结构）。 - build backend MUST 为 `uv_build`. - `uv build` 生成的 wheel/sdist MUST 仅包含运行时必要文件(代码/资源/元数据),不得携带仓库的开发资产目录."
  r5,可选依赖通过 extras 暴露,"系统 MUST 通过 extras 提供 runtime 的可选能力依赖(例如 pandas/excel 等). CLI 拆包后,系统 MUST 满足： - CLI 的运行所需依赖（例如 `jsonschema`）MUST 由 CLI 发行物自身声明并随 CLI 安装满足（不再要求通过 runtime 主包 extras 间接安装）。 - 当用户缺少 CLI 发行物而尝试使用 CLI 能力时，文档与指引 MUST 明确安装 `scalim-cli`（或等价 CLI 发行物）。"
scenarios[12]{req_id,id,given,when,then}:
  r1,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r1,"用户通过-pypi-安装","",用户执行 `pip install PROJECT_DIST_NAME`,Python 环境中应可导入 `PROJECT_DIST_NAME` 根包
  r2,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r2,新导入路径可用,"",调用方执行 `import PROJECT_DIST_NAME`,导入 MUST 成功
  r2,旧导入路径不可用,"",调用方执行 `import PROJECT_DIST_NAME`,导入 MUST 失败(例如抛出 `ModuleNotFoundError`)
  r3,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r3,"cli-可运行","","用户在 Python>=3.10 环境安装并执行 `PROJECT_CLI_NAME --help`",命令 MUST 返回 0 且输出帮助信息
  r4,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r4,"wheel-内容边界可控","","执行 `uv build --wheel`","wheel 顶层 SHOULD 仅包含运行时包目录与对应的 dist-info 元数据"
  r4,"sdist-不包含开发资产目录","","执行 `uv build --sdist`",sdist 中 MUST NOT 包含测试、文档、笔记本、前端、构建产物等非运行时目录
  r5,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r5,"用户安装-runtime-主包不自动获得-cli","",用户仅安装 `PROJECT_DIST_NAME`（不安装 CLI 发行物）,系统 MUST NOT 假设 `PROJECT_CLI_NAME` 命令可用（命令不存在是允许且预期的）
```
