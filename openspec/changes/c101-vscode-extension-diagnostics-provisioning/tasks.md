## 1. Logs / Diagnostic Bundle

- [ ] 1.1 OutputChannel：统一日志分级与入口命令（`Scalim: Open Logs`）
- [ ] 1.2 打开 server log 文件命令（`Scalim: Open Server Log File`）
- [ ] 1.3 `Copy Diagnostic Bundle`：生成可粘贴报告（不包含 YAML 正文）

## 2. Status Bar UX

- [ ] 2.1 Status Bar Item：显示 server 状态 + discovery 摘要（tooltip）
- [ ] 2.2 单击打开 Quick Pick（Logs / Discovery Summary / Restart / Doctor）

## 3. Doctor（预检）

- [ ] 3.1 实现检查项：python 版本、server 安装/版本、scalim.yaml 存在性、yaml.schemas 绑定、server 运行状态
- [ ] 3.2 每项失败提供可操作修复建议（按钮/命令），且必须用户确认后改写 workspace

## 4. Setup Wizard

- [ ] 4.1 provisioning 模式选择：extension venv / workspace venv / PATH
- [ ] 4.2 pinned 版本展示与覆盖输入；确认后执行安装/升级
- [ ] 4.3 成功自动 restart；失败输出可复制错误与回退建议

## 5. scalim.yaml 生命周期

- [ ] 5.1 `Scalim: Open scalim.yaml`（nearest 查找；不存在则引导创建模板）
- [ ] 5.2 File watcher：create/change/delete → 更新 Status Bar + 提示重启（可配置自动重启）

## 6. Validation

- [ ] 6.1 手动冒烟：全新 workspace → Setup Wizard → Doctor 全绿 → Status Bar Running
- [ ] 6.2 手动冒烟：删/改坏 scalim.yaml → Doctor 报首个失败项 → Quick Fix 可修复
- [ ] 6.3 `pnpm -C extras/vscode-scalim lint && pnpm -C extras/vscode-scalim build`
- [ ] 6.4 运行 `just openspec-check`
