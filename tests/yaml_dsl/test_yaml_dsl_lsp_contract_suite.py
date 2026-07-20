import json
import shutil
import sys
import types
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import scalim_yaml_dsl_lsp.cli as lsp_cli

from tests.support.lsp_harness import LspSession, start_yaml_dsl_lsp_server
from tests.support.pathing import fixtures_dir
from tests.support.snapshots import assert_json_snapshot
from tests.support.yaml_dsl_lsp_contracts import (
    assert_no_path_leaks,
    normalize_code_actions,
    normalize_completion_items,
    normalize_diagnostics,
    normalize_hover,
    normalize_json,
    normalize_locations,
)


def _scenario_dir(name: str) -> Path:
    return fixtures_dir() / "yaml_dsl_lsp_contract" / str(name)


def _snapshot_path(scenario: str, filename: str) -> Path:
    return _scenario_dir(scenario) / "snapshots" / str(filename)


def _copy_workspace_fixture(scenario: str, dst: Path) -> None:
    src = _scenario_dir(scenario) / "workspace"
    shutil.copytree(src, dst)


def _pos_of(text: str, needle: str, *, offset: int = 0) -> Tuple[int, int]:
    idx = text.index(str(needle))
    before = text[:idx]
    line = before.count("\n")
    last_nl = before.rfind("\n")
    col = idx if last_nl < 0 else idx - last_nl - 1
    return int(line), int(col) + int(offset)


def _find_code_action(actions: List[Dict[str, Any]], *, command: str) -> Optional[Dict[str, Any]]:
    for action in actions:
        cmd = action.get("command") or {}
        if not isinstance(cmd, dict):
            continue
        if cmd.get("command") == command:
            return action
    return None


def test_dump_discovery_emits_json_payload(tmp_path, capsys) -> None:
    yaml_path = tmp_path / "demo.yaml"
    yaml_path.write_text("loader: demo\n", encoding="utf-8")

    code = lsp_cli.main(["dump-discovery", str(yaml_path), "--json"])
    assert code == 0

    out = capsys.readouterr().out.strip()
    payload = json.loads(out)
    assert payload["project_root"] == str(tmp_path)
    assert payload["python_roots"] == [str(tmp_path)]
    assert payload["allowed_yaml_roots"] == [str(tmp_path)]
    assert payload.get("scalim_yaml_path") is None


def test_serve_missing_dependency_emits_actionable_hints(monkeypatch, capsys) -> None:
    dummy_server = types.ModuleType("scalim_yaml_dsl_lsp.server")
    monkeypatch.setitem(sys.modules, "scalim_yaml_dsl_lsp.server", dummy_server)

    code = lsp_cli.main(["serve", "--log-level", "INFO"])
    assert code == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "uv tool install scalim-yaml-dsl-lsp" in captured.err
    assert "uvx scalim-yaml-dsl-lsp serve --log-level INFO" in captured.err


def test_lsp_contract_python_reference_function(tmp_path) -> None:
    scenario = "python_reference_function"
    workspace = tmp_path / "workspace"
    _copy_workspace_fixture(scenario, workspace)

    yaml_path = workspace / "demo.yaml"
    yaml_text = yaml_path.read_text(encoding="utf-8")

    proc = start_yaml_dsl_lsp_server(workspace)
    session = LspSession(proc, workspace=workspace)
    try:
        session.initialize()
        session.did_open(uri=yaml_path.as_uri(), text=yaml_text)
        diag = session.wait_for_diagnostics(uri=yaml_path.as_uri())
        diag_params = diag.get("params") or {}
        diag_snapshot = {
            "uri": diag_params.get("uri"),
            "diagnostics": normalize_diagnostics(diag_params.get("diagnostics") or []),
        }
        diag_snapshot = normalize_json(diag_snapshot, workspace=workspace)
        assert_no_path_leaks(diag_snapshot, workspace=workspace)
        assert_json_snapshot(_snapshot_path(scenario, "diagnostics.json"), diag_snapshot)

        line, char = _pos_of(yaml_text, "mymod", offset=1)

        locations = session.definition(uri=yaml_path.as_uri(), line=line, character=char) or []
        definition_snapshot = normalize_json(normalize_locations(locations), workspace=workspace)
        assert_no_path_leaks(definition_snapshot, workspace=workspace)
        assert_json_snapshot(_snapshot_path(scenario, "definition.json"), definition_snapshot)

        hover = session.hover(uri=yaml_path.as_uri(), line=line, character=char)
        hover_snapshot = normalize_json(normalize_hover(hover), workspace=workspace)
        assert_no_path_leaks(hover_snapshot, workspace=workspace)
        assert_json_snapshot(_snapshot_path(scenario, "hover.json"), hover_snapshot)
    finally:
        session.shutdown()


def test_lsp_contract_python_reference_object_method(tmp_path) -> None:
    scenario = "python_reference_object_method"
    workspace = tmp_path / "workspace"
    _copy_workspace_fixture(scenario, workspace)

    yaml_path = workspace / "demo.yaml"
    yaml_text = yaml_path.read_text(encoding="utf-8")

    proc = start_yaml_dsl_lsp_server(workspace)
    session = LspSession(proc, workspace=workspace)
    try:
        session.initialize()
        session.did_open(uri=yaml_path.as_uri(), text=yaml_text)
        _ = session.wait_for_diagnostics(uri=yaml_path.as_uri())

        line, char = _pos_of(yaml_text, "some_ref", offset=1)
        locations = session.definition(uri=yaml_path.as_uri(), line=line, character=char) or []
        definition_snapshot = normalize_json(normalize_locations(locations), workspace=workspace)
        assert_no_path_leaks(definition_snapshot, workspace=workspace)
        assert_json_snapshot(_snapshot_path(scenario, "definition.json"), definition_snapshot)
    finally:
        session.shutdown()


def test_lsp_contract_python_completion_module_and_attr(tmp_path) -> None:
    scenario = "python_completion_module_and_attr"
    workspace = tmp_path / "workspace"
    _copy_workspace_fixture(scenario, workspace)

    yaml_path = workspace / "demo.yaml"
    yaml_text = yaml_path.read_text(encoding="utf-8")

    proc = start_yaml_dsl_lsp_server(workspace)
    session = LspSession(proc, workspace=workspace)
    try:
        session.initialize()
        session.did_open(uri=yaml_path.as_uri(), text=yaml_text)
        _ = session.wait_for_diagnostics(uri=yaml_path.as_uri())

        module_line = next(i for i, line in enumerate(yaml_text.splitlines()) if "loader:" in line)
        module_char = int(yaml_text.splitlines()[module_line].index("subpkg")) + 1
        module_items = normalize_completion_items(session.completion(uri=yaml_path.as_uri(), line=module_line, character=module_char))
        module_snapshot = normalize_json(module_items, workspace=workspace)
        assert_no_path_leaks(module_snapshot, workspace=workspace)
        assert_json_snapshot(_snapshot_path(scenario, "completion_module.json"), module_snapshot)

        attr_char = int(yaml_text.splitlines()[module_line].index("load_payment_meth")) + len("load_payment_meth")
        attr_items = normalize_completion_items(session.completion(uri=yaml_path.as_uri(), line=module_line, character=attr_char))
        attr_snapshot = normalize_json(attr_items, workspace=workspace)
        assert_no_path_leaks(attr_snapshot, workspace=workspace)
        assert_json_snapshot(_snapshot_path(scenario, "completion_attr.json"), attr_snapshot)
    finally:
        session.shutdown()


def test_lsp_contract_imports_dollar_import_definition_hover(tmp_path) -> None:
    scenario = "imports_dollar_import_definition_hover"
    workspace = tmp_path / "workspace"
    _copy_workspace_fixture(scenario, workspace)

    yaml_path = workspace / "demo.yaml"
    yaml_text = yaml_path.read_text(encoding="utf-8")

    proc = start_yaml_dsl_lsp_server(workspace)
    session = LspSession(proc, workspace=workspace)
    try:
        session.initialize()
        session.did_open(uri=yaml_path.as_uri(), text=yaml_text)
        _ = session.wait_for_diagnostics(uri=yaml_path.as_uri())

        import_line = next(i for i, line in enumerate(yaml_text.splitlines()) if "$import:" in line)
        import_char = int(yaml_text.splitlines()[import_line].index("fragments")) + 2

        locations = session.definition(uri=yaml_path.as_uri(), line=import_line, character=import_char) or []
        definition_snapshot = normalize_json(normalize_locations(locations), workspace=workspace)
        assert_no_path_leaks(definition_snapshot, workspace=workspace)
        assert_json_snapshot(_snapshot_path(scenario, "definition.json"), definition_snapshot)

        hover = session.hover(uri=yaml_path.as_uri(), line=import_line, character=import_char)
        hover_snapshot = normalize_json(normalize_hover(hover), workspace=workspace)
        assert_no_path_leaks(hover_snapshot, workspace=workspace)
        assert_json_snapshot(_snapshot_path(scenario, "hover.json"), hover_snapshot)
    finally:
        session.shutdown()


def test_lsp_contract_workflow_run_demand_definition(tmp_path) -> None:
    scenario = "workflow_run_demand_definition"
    workspace = tmp_path / "workspace"
    _copy_workspace_fixture(scenario, workspace)

    yaml_path = workspace / "demo.yaml"
    yaml_text = yaml_path.read_text(encoding="utf-8")

    proc = start_yaml_dsl_lsp_server(workspace)
    session = LspSession(proc, workspace=workspace)
    try:
        session.initialize()
        session.did_open(uri=yaml_path.as_uri(), text=yaml_text)
        diag = session.wait_for_diagnostics(uri=yaml_path.as_uri())
        diag_params = diag.get("params") or {}
        diag_snapshot = {
            "uri": diag_params.get("uri"),
            "diagnostics": normalize_diagnostics(diag_params.get("diagnostics") or []),
        }
        diag_snapshot = normalize_json(diag_snapshot, workspace=workspace)
        assert_no_path_leaks(diag_snapshot, workspace=workspace)
        assert_json_snapshot(_snapshot_path(scenario, "diagnostics.json"), diag_snapshot)

        line, char = _pos_of(yaml_text, "d10_paid_orders.demand.yaml", offset=2)
        locations = session.definition(uri=yaml_path.as_uri(), line=line, character=char) or []
        definition_snapshot = normalize_json(normalize_locations(locations), workspace=workspace)
        assert_no_path_leaks(definition_snapshot, workspace=workspace)
        assert_json_snapshot(_snapshot_path(scenario, "definition.json"), definition_snapshot)
    finally:
        session.shutdown()


def test_lsp_contract_builtin_callable_definition_hover_completion(tmp_path) -> None:
    scenario = "builtin_callable_definition_hover_completion"
    workspace = tmp_path / "workspace"
    _copy_workspace_fixture(scenario, workspace)

    yaml_path = workspace / "demo.yaml"
    yaml_text = yaml_path.read_text(encoding="utf-8")

    proc = start_yaml_dsl_lsp_server(workspace)
    session = LspSession(proc, workspace=workspace)
    try:
        session.initialize()
        session.did_open(uri=yaml_path.as_uri(), text=yaml_text)
        _ = session.wait_for_diagnostics(uri=yaml_path.as_uri())

        line_idx = next(i for i, line in enumerate(yaml_text.splitlines()) if "loader:" in line)
        line_text = yaml_text.splitlines()[line_idx]
        cursor_char = int(line_text.index("^workflow")) + len("^work")

        completion_items = normalize_completion_items(session.completion(uri=yaml_path.as_uri(), line=line_idx, character=cursor_char))
        completion_snapshot = normalize_json(completion_items, workspace=workspace)
        assert_no_path_leaks(completion_snapshot, workspace=workspace)
        assert_json_snapshot(_snapshot_path(scenario, "completion.json"), completion_snapshot)

        hover = session.hover(uri=yaml_path.as_uri(), line=line_idx, character=cursor_char)
        hover_snapshot = normalize_json(normalize_hover(hover), workspace=workspace)
        assert_no_path_leaks(hover_snapshot, workspace=workspace)
        assert_json_snapshot(_snapshot_path(scenario, "hover.json"), hover_snapshot)

        locations = session.definition(uri=yaml_path.as_uri(), line=line_idx, character=cursor_char) or []
        definition_snapshot = normalize_json(normalize_locations(locations), workspace=workspace)
        assert_no_path_leaks(definition_snapshot, workspace=workspace)
        assert_json_snapshot(_snapshot_path(scenario, "definition.json"), definition_snapshot)
    finally:
        session.shutdown()


def test_lsp_contract_outputs_fields_completion_and_definition(tmp_path) -> None:
    scenario = "outputs_fields_completion_and_definition"
    workspace = tmp_path / "workspace"
    _copy_workspace_fixture(scenario, workspace)

    yaml_path = workspace / "demo.yaml"
    yaml_text = yaml_path.read_text(encoding="utf-8")

    proc = start_yaml_dsl_lsp_server(workspace)
    session = LspSession(proc, workspace=workspace)
    try:
        session.initialize()
        session.did_open(uri=yaml_path.as_uri(), text=yaml_text)
        _ = session.wait_for_diagnostics(uri=yaml_path.as_uri())

        lines = yaml_text.splitlines()
        empty_item_line = next(idx for idx, line in enumerate(lines) if line.strip() == "-")
        empty_item_char = len(lines[empty_item_line])
        completion_items = normalize_completion_items(
            session.completion(uri=yaml_path.as_uri(), line=empty_item_line, character=empty_item_char)
        )
        completion_snapshot = normalize_json(completion_items, workspace=workspace)
        assert_no_path_leaks(completion_snapshot, workspace=workspace)
        assert_json_snapshot(_snapshot_path(scenario, "completion_empty_item.json"), completion_snapshot)

        out_fields_line = next(idx for idx, line in enumerate(lines) if line.strip() == "- b")
        b_char = int(lines[out_fields_line].index("b"))
        locations = session.definition(uri=yaml_path.as_uri(), line=out_fields_line, character=b_char) or []
        definition_snapshot = normalize_json(normalize_locations(locations), workspace=workspace)
        assert_no_path_leaks(definition_snapshot, workspace=workspace)
        assert_json_snapshot(_snapshot_path(scenario, "definition_b.json"), definition_snapshot)
    finally:
        session.shutdown()


def test_lsp_contract_yaml_alias_definition_hover(tmp_path) -> None:
    scenario = "yaml_alias_definition_hover"
    workspace = tmp_path / "workspace"
    _copy_workspace_fixture(scenario, workspace)

    yaml_path = workspace / "demo.yaml"
    yaml_text = yaml_path.read_text(encoding="utf-8")

    proc = start_yaml_dsl_lsp_server(workspace)
    session = LspSession(proc, workspace=workspace)
    try:
        session.initialize()
        session.did_open(uri=yaml_path.as_uri(), text=yaml_text)
        _ = session.wait_for_diagnostics(uri=yaml_path.as_uri())

        alias_line = next(idx for idx, line in enumerate(yaml_text.splitlines()) if "*detail_fields" in line)
        cursor_char = int(yaml_text.splitlines()[alias_line].index("detail_fields")) + 2

        locations = session.definition(uri=yaml_path.as_uri(), line=alias_line, character=cursor_char) or []
        definition_snapshot = normalize_json(normalize_locations(locations), workspace=workspace)
        assert_no_path_leaks(definition_snapshot, workspace=workspace)
        assert_json_snapshot(_snapshot_path(scenario, "definition.json"), definition_snapshot)

        hover = session.hover(uri=yaml_path.as_uri(), line=alias_line, character=cursor_char)
        hover_snapshot = normalize_json(normalize_hover(hover), workspace=workspace)
        assert_no_path_leaks(hover_snapshot, workspace=workspace)
        assert_json_snapshot(_snapshot_path(scenario, "hover.json"), hover_snapshot)
    finally:
        session.shutdown()


def test_lsp_contract_code_actions_create_minimal_scalim_yaml(tmp_path) -> None:
    scenario = "code_actions_create_minimal_scalim_yaml"
    workspace = tmp_path / "workspace"
    _copy_workspace_fixture(scenario, workspace)

    yaml_path = workspace / "demo.yaml"
    yaml_text = yaml_path.read_text(encoding="utf-8")

    proc = start_yaml_dsl_lsp_server(workspace)
    session = LspSession(proc, workspace=workspace)
    try:
        session.initialize()
        session.did_open(uri=yaml_path.as_uri(), text=yaml_text)
        _ = session.wait_for_diagnostics(uri=yaml_path.as_uri())

        actions_raw = session.code_actions(uri=yaml_path.as_uri(), line=0, character=0) or []
        actions = normalize_code_actions(actions_raw)
        snapshot = normalize_json(actions, workspace=workspace)
        assert_no_path_leaks(snapshot, workspace=workspace)
        assert_json_snapshot(_snapshot_path(scenario, "code_actions.json"), snapshot)

        create_action = _find_code_action(actions_raw, command="scalim.yaml.createMinimal")
        assert create_action is not None
        cmd = create_action.get("command") or {}
        session.execute_command(str(cmd.get("command") or ""), list(cmd.get("arguments") or []))

        scalim_yaml = workspace / "scalim.yaml"
        assert scalim_yaml.exists()
        content = scalim_yaml.read_text(encoding="utf-8")
        assert "yaml_dsl:" in content

        scalim_yaml_snapshot = normalize_json({"content": str(content)}, workspace=workspace)
        assert_no_path_leaks(scalim_yaml_snapshot, workspace=workspace)
        assert_json_snapshot(_snapshot_path(scenario, "scalim_yaml.json"), scalim_yaml_snapshot)
    finally:
        session.shutdown()


def test_lsp_contract_books_unified_xlsx_diagnostics(tmp_path) -> None:
    scenario = "books_unified_xlsx_diagnostics"
    workspace = tmp_path / "workspace"
    _copy_workspace_fixture(scenario, workspace)

    yaml_path = workspace / "demo.yaml"
    yaml_text = yaml_path.read_text(encoding="utf-8")

    proc = start_yaml_dsl_lsp_server(workspace)
    session = LspSession(proc, workspace=workspace)
    try:
        session.initialize()
        session.did_open(uri=yaml_path.as_uri(), text=yaml_text)
        diag = session.wait_for_diagnostics(uri=yaml_path.as_uri())
        diag_params = diag.get("params") or {}
        diag_snapshot = {
            "uri": diag_params.get("uri"),
            "diagnostics": normalize_diagnostics(diag_params.get("diagnostics") or []),
        }
        diag_snapshot = normalize_json(diag_snapshot, workspace=workspace)
        assert_no_path_leaks(diag_snapshot, workspace=workspace)
        assert_json_snapshot(_snapshot_path(scenario, "diagnostics.json"), diag_snapshot)
        assert diag_snapshot["diagnostics"] == []
    finally:
        session.shutdown()


def test_lsp_contract_books_removed_alias_diagnostics(tmp_path) -> None:
    scenario = "books_removed_alias_diagnostics"
    workspace = tmp_path / "workspace"
    _copy_workspace_fixture(scenario, workspace)

    yaml_path = workspace / "demo.yaml"
    yaml_text = yaml_path.read_text(encoding="utf-8")

    proc = start_yaml_dsl_lsp_server(workspace)
    session = LspSession(proc, workspace=workspace)
    try:
        session.initialize()
        session.did_open(uri=yaml_path.as_uri(), text=yaml_text)
        diag = session.wait_for_diagnostics(uri=yaml_path.as_uri())
        diag_params = diag.get("params") or {}
        diag_snapshot = {
            "uri": diag_params.get("uri"),
            "diagnostics": normalize_diagnostics(diag_params.get("diagnostics") or []),
        }
        diag_snapshot = normalize_json(diag_snapshot, workspace=workspace)
        assert_no_path_leaks(diag_snapshot, workspace=workspace)
        assert_json_snapshot(_snapshot_path(scenario, "diagnostics.json"), diag_snapshot)

        messages = [str(item.get("message") or "") for item in diag_snapshot["diagnostics"]]
        assert any("xlsx_file was removed" in msg for msg in messages)
        assert any("xlsx_memory was removed" in msg for msg in messages)
    finally:
        session.shutdown()


def test_lsp_contract_workflow_books_removed_alias_diagnostics(tmp_path) -> None:
    scenario = "workflow_books_removed_alias_diagnostics"
    workspace = tmp_path / "workspace"
    _copy_workspace_fixture(scenario, workspace)

    yaml_path = workspace / "demo.yaml"
    yaml_text = yaml_path.read_text(encoding="utf-8")

    proc = start_yaml_dsl_lsp_server(workspace)
    session = LspSession(proc, workspace=workspace)
    try:
        session.initialize()
        session.did_open(uri=yaml_path.as_uri(), text=yaml_text)
        diag = session.wait_for_diagnostics(uri=yaml_path.as_uri())
        diag_params = diag.get("params") or {}
        diag_snapshot = {
            "uri": diag_params.get("uri"),
            "diagnostics": normalize_diagnostics(diag_params.get("diagnostics") or []),
        }
        diag_snapshot = normalize_json(diag_snapshot, workspace=workspace)
        assert_no_path_leaks(diag_snapshot, workspace=workspace)
        assert_json_snapshot(_snapshot_path(scenario, "diagnostics.json"), diag_snapshot)

        messages = [str(item.get("message") or "") for item in diag_snapshot["diagnostics"]]
        assert any("xlsx_file" in msg for msg in messages)
    finally:
        session.shutdown()
