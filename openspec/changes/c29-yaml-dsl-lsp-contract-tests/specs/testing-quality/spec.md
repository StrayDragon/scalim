## MODIFIED Requirements

### Requirement: YAML DSL LSP MUST have protocol-level contract tests as a refactor baseline

当我们对 YAML DSL 的实现进行大规模重构（例如把 editor semantics 收敛为编译前端 SSOT）时，系统 MUST 通过协议级（JSON-RPC/LSP）contract tests 来验证行为没有无意漂移。

contract tests MUST：

- MUST 启动真实的 `scalim-yaml-dsl-lsp serve`（stdio）作为被测对象，而不是只调用内部函数。
- MUST 覆盖至少以下 endpoint 的关键路径：
  - `textDocument/publishDiagnostics`（didOpen/didChange 触发）
  - `textDocument/definition`
  - `textDocument/hover`
  - `textDocument/completion`
  - `textDocument/codeAction` 与 `workspace/executeCommand`
- MUST 具备跨环境稳定性（见下一个 requirement 的 normalize 要求）。

#### Scenario: run contract tests before and after a refactor

- **GIVEN** 一组固定的 LSP contract fixtures（包含 YAML、imports、以及必要的 Python 模块文件）
- **WHEN** 在 refactor 前后分别运行对应的测试套件
- **THEN** contract tests MUST 在两次运行中都通过
- **AND** 若行为发生变化，必须通过更新 golden/snapshots 或变更说明显式确认

### Requirement: LSP contract tests MUST normalize environment-specific paths and ordering

为了避免因 CI/tmp 目录差异导致的脆弱失败，contract tests MUST 对协议输出做稳定化处理：

- MUST 将 workspace 的绝对路径从 snapshots 中移除（例如用 `<WORKSPACE>` placeholder 表示根路径）。
- MUST 对 diagnostics/completions/locations 做稳定排序（避免由于内部 map/set 顺序变化导致的非行为性漂移）。

#### Scenario: snapshots do not embed tmp absolute paths

- **GIVEN** contract tests 在随机 `tmp_path` 下创建 workspace
- **WHEN** 生成/对拍 snapshots
- **THEN** snapshots MUST NOT 包含 `tmp_path` 的绝对路径字符串
