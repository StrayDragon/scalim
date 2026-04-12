# sinks-contracts Specification

## ADDED Requirements

### Requirement: built-in file sinks MUST NOT create adjacent `.scalim.lock` files

系统内建 file sinks（例如 CSV/Excel）在写出边界 MUST NOT 通过在目标输出路径旁创建 `<output_path>.scalim.lock` 的方式实现并发保护。

说明：

- 并发隔离应优先通过“版本化输出（D-2）+ 唯一路径”在更高层解决。
- 若调用方仍需要对固定路径做互斥，系统 SHALL 建议调用方在框架外部进行协调（例如业务层唯一输出路径、外部锁或排队）。

#### Scenario: sink close does not leave a lock file next to output
- **GIVEN** 某次 CSV/Excel sink 写出目标路径为 `./out/report.csv` 或 `./out/report.xlsx`
- **WHEN** sink 成功 close 并发布最终文件
- **THEN** `./out/report.csv.scalim.lock` 与 `./out/report.xlsx.scalim.lock` MUST NOT 存在

## REMOVED Requirements

### Requirement: file sinks 支持可选的并发写出保护(避免静默覆盖)

**Reason**：lockfile 并发保护会在用户目录制造额外文件并在服务端多并发请求下引入冲突/残留风险；版本化输出（D-2）已提供更干净的并发隔离方式。

**Migration**：

- 使用版本化输出 root：每次运行写入独立版本目录，并通过 `manifest/latest.json` 获取稳定入口。
- 若必须写固定路径（不推荐），由调用方在框架外部提供互斥/调度。

#### Scenario: concurrent writers rely on version isolation instead of lockfiles
- **GIVEN** 两个独立运行需要同时生成报表
- **WHEN** 两个运行写入同一输出 root 的不同 `version_id`
- **THEN** 系统 MUST 允许两次写入并存
- **AND** 系统 MUST NOT 使用 lockfile 作为并发保护机制

