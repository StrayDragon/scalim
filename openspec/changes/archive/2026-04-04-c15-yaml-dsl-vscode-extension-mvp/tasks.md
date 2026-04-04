## 1. 工程脚手架与基础配置

- [x] 1.1 扩展工程固定在 `extras/vscode-scalim/`（pnpm + esbuild）；补齐 `package.json` 的 contributes/activationEvents
- [x] 1.2 输出日志通道：`Scalim YAML DSL`（OutputChannel），并把 provisioning / server 启动 / crash 信息写入
- [x] 1.3 提供 `fixtures/`（最小 `scalim.yaml` + demand/workflow 示例 YAML），用于手动验证

## 2. Schema 协作（redhat.vscode-yaml）

- [x] 2.1 通过 pinned venv 内的 `scalim-cli yaml-dsl schema path --type ...` 解析 schema 绝对路径（scalim_yaml/demand/workflow）
- [x] 2.2 以 **idempotent merge** 方式写入工作区 `yaml.schemas`（scalim.yaml / demand/**/*.y*ml / workflow/**/*.y*ml）；缺少 `redhat.vscode-yaml` 时降级并提示安装
- [x] 2.3（可选）提供开关禁用自动 schema 绑定（避免改动工作区 settings）

## 3. Venv provisioning（pinned）

- [x] 3.1 探测 Python >=3.10（支持配置覆盖 python 路径）；失败时输出可诊断提示
- [x] 3.2 在 `globalStorageUri` 创建/复用 venv（单机复用）；写入 meta（python 路径/版本、pinned pip spec）
- [x] 3.3 安装 pinned server 发行物（默认 `scalim-yaml-dsl-lsp[server]==0.7.5`）；失败时输出 pip 命令与 stderr 摘要
- [x] 3.4 命令：Reinstall server（重建 venv + 重新安装 pinned）

## 4. LSP server lifecycle

- [x] 4.1 使用 stdio 启动 server（遵循 `yaml-dsl-lsp-serve`；优先 `<venv>/bin/scalim-yaml-dsl-lsp serve`）
- [x] 4.2 管理生命周期：启动、崩溃提示、最小 restart 命令
- [x] 4.3 输出 diagnostics：venv 路径、python 版本、server 版本、对当前活动 YAML 的 discovery 摘要（`scalim-yaml-dsl-lsp dump-discovery ... --json`）

## 5. 验证

- [x] 5.1 本地开发安装验证：F5 启动 Extension Host，打开 `fixtures/` 内 YAML，能看到 schema + LSP diagnostics；日志可定位到具体 workspace
- [x] 5.2 运行 `just openspec-check` 确认 OpenSpec 工件结构与 schema 校验通过
