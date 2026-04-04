## 1. 工程脚手架与基础配置

- [ ] 1.1 确定扩展工程目录位置与构建方式（TypeScript + VSCode Extension API）
- [ ] 1.2 定义 activation events（匹配 YAML DSL 文件或命令触发）与输出日志通道

## 2. Schema 协作（redhat.vscode-yaml）

- [ ] 2.1 读取/推导 demand/workflow 文件匹配规则（基于 project discovery）
- [ ] 2.2 配置 `yaml.schemas` 绑定 demand/workflow schema（不替换 YAML 插件）

## 3. Venv provisioning（pinned）

- [ ] 3.1 在 `globalStorageUri` 创建/复用 venv
- [ ] 3.2 安装 pinned server 发行物（默认 `scalim-yaml-dsl-lsp[server]`）；失败时输出可诊断信息
- [ ] 3.3 提供最小重装/修复路径（例如命令：Reinstall server）

## 4. LSP server lifecycle

- [ ] 4.1 以 stdio 启动 server（遵循 `yaml-dsl-lsp-serve`）
- [ ] 4.2 管理生命周期：启动、崩溃提示、重启命令（MVP 最小）
- [ ] 4.3 输出 diagnostics：当前 venv 路径、server 版本、discovery 摘要

## 5. 验证

- [ ] 5.1 本地开发安装验证：打开 fixtures YAML 能看到 schema + LSP diagnostics
- [ ] 5.2 运行 `just openspec-check` 确认 OpenSpec 工件结构与 schema 校验通过

