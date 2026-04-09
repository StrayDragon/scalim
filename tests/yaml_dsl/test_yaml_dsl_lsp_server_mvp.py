import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import scalim_yaml_dsl_lsp.cli as lsp_cli


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


def test_lsp_server_publishes_diagnostics_and_resolves_definition(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    module_path = workspace / "mymod.py"
    module_path.write_text(
        "\n".join(
            [
                "def myfunc() -> int:",
                '    """demo docstring"""',
                "    return 1",
                "",
            ]
        ),
        encoding="utf-8",
    )

    yaml_path = workspace / "demo.yaml"
    yaml_text = "loader: mymod:myfunc\n"
    yaml_path.write_text(yaml_text, encoding="utf-8")

    proc = _start_lsp_server_process(workspace)
    client = _LspClient(proc)
    try:
        init_id = client.send_request(
            "initialize",
            {
                "processId": None,
                "rootUri": workspace.as_uri(),
                "capabilities": {},
                "workspaceFolders": [{"uri": workspace.as_uri(), "name": "workspace"}],
            },
        )
        init_resp = client.recv_until(lambda msg: msg.get("id") == init_id, timeout=10.0)
        assert "error" not in init_resp
        assert "result" in init_resp

        client.send_notification("initialized", {})

        client.send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": yaml_path.as_uri(),
                    "languageId": "yaml",
                    "version": 1,
                    "text": yaml_text,
                }
            },
        )

        pub = client.recv_until(
            lambda msg: msg.get("method") == "textDocument/publishDiagnostics",
            timeout=10.0,
        )
        assert pub["params"]["uri"] == yaml_path.as_uri()

        line0 = yaml_text.splitlines()[0]
        cursor_char = int(line0.index("mymod")) + 1
        definition_id = client.send_request(
            "textDocument/definition",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": 0, "character": cursor_char},
            },
        )
        definition_resp = client.recv_until(lambda msg: msg.get("id") == definition_id, timeout=10.0)
        assert "error" not in definition_resp

        locations = definition_resp.get("result") or []
        assert isinstance(locations, list)
        assert any(loc.get("uri") == module_path.as_uri() for loc in locations)
    finally:
        client.shutdown()


def test_lsp_server_definition_returns_multiple_locations_for_object_method(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    module_path = workspace / "mymod.py"
    module_path.write_text(
        "\n".join(
            [
                "class Klass:",
                "    def a_method(self) -> int:",
                "        return 1",
                "",
                "some_ref = Klass()",
                "",
            ]
        ),
        encoding="utf-8",
    )

    yaml_path = workspace / "demo.yaml"
    yaml_text = "loader: mymod:some_ref.a_method\n"
    yaml_path.write_text(yaml_text, encoding="utf-8")

    proc = _start_lsp_server_process(workspace)
    client = _LspClient(proc)
    try:
        init_id = client.send_request(
            "initialize",
            {
                "processId": None,
                "rootUri": workspace.as_uri(),
                "capabilities": {},
                "workspaceFolders": [{"uri": workspace.as_uri(), "name": "workspace"}],
            },
        )
        init_resp = client.recv_until(lambda msg: msg.get("id") == init_id, timeout=10.0)
        assert "error" not in init_resp

        client.send_notification("initialized", {})

        client.send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": yaml_path.as_uri(),
                    "languageId": "yaml",
                    "version": 1,
                    "text": yaml_text,
                }
            },
        )
        _ = client.recv_until(lambda msg: msg.get("method") == "textDocument/publishDiagnostics", timeout=10.0)

        line0 = yaml_text.splitlines()[0]
        cursor_char = int(line0.index("some_ref")) + 1
        definition_id = client.send_request(
            "textDocument/definition",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": 0, "character": cursor_char},
            },
        )
        definition_resp = client.recv_until(lambda msg: msg.get("id") == definition_id, timeout=10.0)
        assert "error" not in definition_resp

        locations = definition_resp.get("result") or []
        assert isinstance(locations, list)
        assert len(locations) >= 2
        assert locations[0].get("uri") == module_path.as_uri()
        assert locations[0].get("range", {}).get("start", {}).get("line") == 1  # def a_method
        assert locations[1].get("uri") == module_path.as_uri()
    finally:
        client.shutdown()


def test_lsp_server_completes_module_and_symbol_segments(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    pkg_dir = workspace / "scalim_misc" / "demo_big_data_report"
    pkg_dir.mkdir(parents=True)
    (workspace / "scalim_misc" / "__init__.py").write_text("", encoding="utf-8")
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
    (pkg_dir / "loaders.py").write_text(
        "\n".join(
            [
                "def load_payment_methods() -> int:",
                "    return 1",
                "",
            ]
        ),
        encoding="utf-8",
    )

    yaml_path = workspace / "demo.yaml"
    yaml_text = 'payment_methods:\n  loader: "scalim_misc.demo_big_data_report.loaders:load_payment_meth"\n'
    yaml_path.write_text(yaml_text, encoding="utf-8")

    proc = _start_lsp_server_process(workspace)
    client = _LspClient(proc)
    try:
        init_id = client.send_request(
            "initialize",
            {
                "processId": None,
                "rootUri": workspace.as_uri(),
                "capabilities": {},
                "workspaceFolders": [{"uri": workspace.as_uri(), "name": "workspace"}],
            },
        )
        init_resp = client.recv_until(lambda msg: msg.get("id") == init_id, timeout=10.0)
        assert "error" not in init_resp

        client.send_notification("initialized", {})

        client.send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": yaml_path.as_uri(),
                    "languageId": "yaml",
                    "version": 1,
                    "text": yaml_text,
                }
            },
        )
        _ = client.recv_until(lambda msg: msg.get("method") == "textDocument/publishDiagnostics", timeout=10.0)

        line0 = yaml_text.splitlines()[1]
        module_cursor_char = int(line0.index("demo_big_data_report")) + len("demo_big_data_re")
        module_completion_id = client.send_request(
            "textDocument/completion",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": 1, "character": module_cursor_char},
            },
        )
        module_resp = client.recv_until(lambda msg: msg.get("id") == module_completion_id, timeout=10.0)
        assert "error" not in module_resp
        module_items = module_resp.get("result", {}).get("items", [])
        module_labels = {item.get("label") for item in module_items}
        assert "demo_big_data_report" in module_labels

        attr_cursor_char = int(line0.index("load_payment_meth")) + len("load_payment_meth")
        attr_completion_id = client.send_request(
            "textDocument/completion",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": 1, "character": attr_cursor_char},
            },
        )
        attr_resp = client.recv_until(lambda msg: msg.get("id") == attr_completion_id, timeout=10.0)
        assert "error" not in attr_resp
        attr_items = attr_resp.get("result", {}).get("items", [])
        attr_labels = {item.get("label") for item in attr_items}
        assert "load_payment_methods" in attr_labels
    finally:
        client.shutdown()


def test_lsp_server_resolves_import_definition_and_hover(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    fragment_path = workspace / "ecommerce_report_fragments.yaml"
    fragment_text = "\n".join(
        [
            "report_book:",
            "  kind: xlsx_file",
            "  path: ./out.xlsx",
            "",
        ]
    )
    fragment_path.write_text(fragment_text, encoding="utf-8")

    yaml_path = workspace / "demo.yaml"
    yaml_text = "\n".join(
        [
            "imports:",
            "  fragments: ./ecommerce_report_fragments.yaml",
            "resources:",
            "  books:",
            "    report:",
            "      $import: fragments.report_book",
            "",
        ]
    )
    yaml_path.write_text(yaml_text, encoding="utf-8")

    proc = _start_lsp_server_process(workspace)
    client = _LspClient(proc)
    try:
        init_id = client.send_request(
            "initialize",
            {
                "processId": None,
                "rootUri": workspace.as_uri(),
                "capabilities": {},
                "workspaceFolders": [{"uri": workspace.as_uri(), "name": "workspace"}],
            },
        )
        init_resp = client.recv_until(lambda msg: msg.get("id") == init_id, timeout=10.0)
        assert "error" not in init_resp

        client.send_notification("initialized", {})
        client.send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": yaml_path.as_uri(),
                    "languageId": "yaml",
                    "version": 1,
                    "text": yaml_text,
                }
            },
        )
        _ = client.recv_until(lambda msg: msg.get("method") == "textDocument/publishDiagnostics", timeout=10.0)

        lines = yaml_text.splitlines()
        import_line = next(idx for idx, line in enumerate(lines) if "$import:" in line)
        cursor_char = int(lines[import_line].index("fragments")) + 2

        definition_id = client.send_request(
            "textDocument/definition",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": import_line, "character": cursor_char},
            },
        )
        definition_resp = client.recv_until(lambda msg: msg.get("id") == definition_id, timeout=10.0)
        assert "error" not in definition_resp

        locations = definition_resp.get("result") or []
        assert isinstance(locations, list)
        assert any(loc.get("uri") == fragment_path.as_uri() for loc in locations)

        hover_id = client.send_request(
            "textDocument/hover",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": import_line, "character": cursor_char},
            },
        )
        hover_resp = client.recv_until(lambda msg: msg.get("id") == hover_id, timeout=10.0)
        assert "error" not in hover_resp
        hover = hover_resp.get("result") or {}
        value = (hover.get("contents") or {}).get("value") if isinstance(hover, dict) else ""
        assert isinstance(value, str)
        assert str(fragment_path) in value
    finally:
        client.shutdown()


def test_lsp_server_import_definition_unknown_alias_degrades_to_empty(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    yaml_path = workspace / "demo.yaml"
    yaml_text = "\n".join(
        [
            "resources:",
            "  books:",
            "    report:",
            "      $import: fragments.report_book",
            "",
        ]
    )
    yaml_path.write_text(yaml_text, encoding="utf-8")

    proc = _start_lsp_server_process(workspace)
    client = _LspClient(proc)
    try:
        init_id = client.send_request(
            "initialize",
            {
                "processId": None,
                "rootUri": workspace.as_uri(),
                "capabilities": {},
                "workspaceFolders": [{"uri": workspace.as_uri(), "name": "workspace"}],
            },
        )
        init_resp = client.recv_until(lambda msg: msg.get("id") == init_id, timeout=10.0)
        assert "error" not in init_resp

        client.send_notification("initialized", {})
        client.send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": yaml_path.as_uri(),
                    "languageId": "yaml",
                    "version": 1,
                    "text": yaml_text,
                }
            },
        )
        _ = client.recv_until(lambda msg: msg.get("method") == "textDocument/publishDiagnostics", timeout=10.0)

        line0 = yaml_text.splitlines()[3]
        cursor_char = int(line0.index("fragments")) + 2
        definition_id = client.send_request(
            "textDocument/definition",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": 3, "character": cursor_char},
            },
        )
        definition_resp = client.recv_until(lambda msg: msg.get("id") == definition_id, timeout=10.0)
        assert "error" not in definition_resp
        assert not definition_resp.get("result")
    finally:
        client.shutdown()


def test_lsp_server_import_definition_path_escapes_allowed_roots_degrades_to_empty(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    outside = tmp_path / "outside.yaml"
    outside.write_text("report_book: {kind: xlsx_file}\n", encoding="utf-8")

    yaml_path = workspace / "demo.yaml"
    yaml_text = "\n".join(
        [
            "imports:",
            "  fragments: ../outside.yaml",
            "resources:",
            "  books:",
            "    report:",
            "      $import: fragments.report_book",
            "",
        ]
    )
    yaml_path.write_text(yaml_text, encoding="utf-8")

    proc = _start_lsp_server_process(workspace)
    client = _LspClient(proc)
    try:
        init_id = client.send_request(
            "initialize",
            {
                "processId": None,
                "rootUri": workspace.as_uri(),
                "capabilities": {},
                "workspaceFolders": [{"uri": workspace.as_uri(), "name": "workspace"}],
            },
        )
        init_resp = client.recv_until(lambda msg: msg.get("id") == init_id, timeout=10.0)
        assert "error" not in init_resp

        client.send_notification("initialized", {})
        client.send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": yaml_path.as_uri(),
                    "languageId": "yaml",
                    "version": 1,
                    "text": yaml_text,
                }
            },
        )
        _ = client.recv_until(lambda msg: msg.get("method") == "textDocument/publishDiagnostics", timeout=10.0)

        line0 = yaml_text.splitlines()[5]
        cursor_char = int(line0.index("fragments")) + 2
        definition_id = client.send_request(
            "textDocument/definition",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": 5, "character": cursor_char},
            },
        )
        definition_resp = client.recv_until(lambda msg: msg.get("id") == definition_id, timeout=10.0)
        assert "error" not in definition_resp
        assert not definition_resp.get("result")
    finally:
        client.shutdown()


def test_lsp_server_builtin_callable_definition_hover_and_completion(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    yaml_path = workspace / "demo.yaml"
    yaml_text = "\n".join(
        [
            "name: demo",
            "main_source:",
            "  source_id: orders",
            "  loader: ^workflow/book_sheet_rows",
            "  fields: {a: {}}",
            "outputs: []",
            "",
        ]
    )
    yaml_path.write_text(yaml_text, encoding="utf-8")

    proc = _start_lsp_server_process(workspace)
    client = _LspClient(proc)
    try:
        init_id = client.send_request(
            "initialize",
            {
                "processId": None,
                "rootUri": workspace.as_uri(),
                "capabilities": {},
                "workspaceFolders": [{"uri": workspace.as_uri(), "name": "workspace"}],
            },
        )
        init_resp = client.recv_until(lambda msg: msg.get("id") == init_id, timeout=10.0)
        assert "error" not in init_resp

        client.send_notification("initialized", {})
        client.send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": yaml_path.as_uri(),
                    "languageId": "yaml",
                    "version": 1,
                    "text": yaml_text,
                }
            },
        )
        _ = client.recv_until(lambda msg: msg.get("method") == "textDocument/publishDiagnostics", timeout=10.0)

        line_idx = next(i for i, line in enumerate(yaml_text.splitlines()) if "loader:" in line)
        line_text = yaml_text.splitlines()[line_idx]
        cursor_char = int(line_text.index("^workflow")) + len("^work")

        completion_id = client.send_request(
            "textDocument/completion",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": line_idx, "character": cursor_char},
            },
        )
        completion_resp = client.recv_until(lambda msg: msg.get("id") == completion_id, timeout=10.0)
        assert "error" not in completion_resp
        items = completion_resp.get("result", {}).get("items", [])
        labels = {item.get("label") for item in items}
        assert "workflow/book_sheet_rows" in labels

        hover_id = client.send_request(
            "textDocument/hover",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": line_idx, "character": cursor_char},
            },
        )
        hover_resp = client.recv_until(lambda msg: msg.get("id") == hover_id, timeout=10.0)
        assert "error" not in hover_resp
        hover = hover_resp.get("result") or {}
        value = (hover.get("contents") or {}).get("value") if isinstance(hover, dict) else ""
        assert isinstance(value, str)
        assert "builtin:" in value
        assert "workflow/book_sheet_rows" in value

        definition_id = client.send_request(
            "textDocument/definition",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": line_idx, "character": cursor_char},
            },
        )
        definition_resp = client.recv_until(lambda msg: msg.get("id") == definition_id, timeout=10.0)
        assert "error" not in definition_resp

        import scalim.workflow.loaders as loaders

        expected_uri = Path(str(loaders.__file__)).resolve().as_uri()
        locations = definition_resp.get("result") or []
        assert any(loc.get("uri") == expected_uri for loc in locations)
    finally:
        client.shutdown()


def test_lsp_server_outputs_fields_definition_and_hover_same_file(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    yaml_path = workspace / "demo.yaml"
    yaml_text = "\n".join(
        [
            "name: demo",
            "main_source:",
            "  source_id: orders",
            "  loader: tests.fixtures.mock_loaders.mock_loader",
            "  fields:",
            "    a: {name: A}",
            "sources: {}",
            "fields:",
            "  b:",
            '    compute: "1"',
            "outputs:",
            "  - name: out",
            "    to: {file: out.xlsx}",
            "    fields:",
            "      - a",
            "      - b",
            "",
        ]
    )
    yaml_path.write_text(yaml_text, encoding="utf-8")

    proc = _start_lsp_server_process(workspace)
    client = _LspClient(proc)
    try:
        init_id = client.send_request(
            "initialize",
            {
                "processId": None,
                "rootUri": workspace.as_uri(),
                "capabilities": {},
                "workspaceFolders": [{"uri": workspace.as_uri(), "name": "workspace"}],
            },
        )
        init_resp = client.recv_until(lambda msg: msg.get("id") == init_id, timeout=10.0)
        assert "error" not in init_resp

        client.send_notification("initialized", {})
        client.send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": yaml_path.as_uri(),
                    "languageId": "yaml",
                    "version": 1,
                    "text": yaml_text,
                }
            },
        )
        _ = client.recv_until(lambda msg: msg.get("method") == "textDocument/publishDiagnostics", timeout=10.0)

        lines = yaml_text.splitlines()
        out_fields_line = next(idx for idx, line in enumerate(lines) if line.strip() == "- b")
        cursor_char = int(lines[out_fields_line].index("b"))

        definition_id = client.send_request(
            "textDocument/definition",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": out_fields_line, "character": cursor_char},
            },
        )
        definition_resp = client.recv_until(lambda msg: msg.get("id") == definition_id, timeout=10.0)
        assert "error" not in definition_resp
        locations = definition_resp.get("result") or []
        assert isinstance(locations, list)
        assert any(loc.get("uri") == yaml_path.as_uri() for loc in locations)

        hover_id = client.send_request(
            "textDocument/hover",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": out_fields_line, "character": cursor_char},
            },
        )
        hover_resp = client.recv_until(lambda msg: msg.get("id") == hover_id, timeout=10.0)
        assert "error" not in hover_resp
        hover = hover_resp.get("result") or {}
        value = (hover.get("contents") or {}).get("value") if isinstance(hover, dict) else ""
        assert isinstance(value, str)
        assert "Field:" in value
        assert "b" in value
    finally:
        client.shutdown()


def test_lsp_server_outputs_fields_completion_empty_list_item(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    yaml_path = workspace / "demo.yaml"
    yaml_text = "\n".join(
        [
            "name: demo",
            "main_source:",
            "  source_id: orders",
            "  loader: tests.fixtures.mock_loaders.mock_loader",
            "  fields:",
            "    a: {name: A}",
            "sources: {}",
            "fields:",
            "  b:",
            '    compute: "1"',
            "outputs:",
            "  - name: out",
            "    to: {file: out.xlsx}",
            "    fields:",
            "      -  ",
            "",
        ]
    )
    yaml_path.write_text(yaml_text, encoding="utf-8")

    proc = _start_lsp_server_process(workspace)
    client = _LspClient(proc)
    try:
        init_id = client.send_request(
            "initialize",
            {
                "processId": None,
                "rootUri": workspace.as_uri(),
                "capabilities": {},
                "workspaceFolders": [{"uri": workspace.as_uri(), "name": "workspace"}],
            },
        )
        init_resp = client.recv_until(lambda msg: msg.get("id") == init_id, timeout=10.0)
        assert "error" not in init_resp

        client.send_notification("initialized", {})
        client.send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": yaml_path.as_uri(),
                    "languageId": "yaml",
                    "version": 1,
                    "text": yaml_text,
                }
            },
        )
        _ = client.recv_until(lambda msg: msg.get("method") == "textDocument/publishDiagnostics", timeout=10.0)

        lines = yaml_text.splitlines()
        empty_item_line = next(idx for idx, line in enumerate(lines) if line.strip() == "-")
        cursor_char = len(lines[empty_item_line])

        completion_id = client.send_request(
            "textDocument/completion",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": empty_item_line, "character": cursor_char},
            },
        )
        completion_resp = client.recv_until(lambda msg: msg.get("id") == completion_id, timeout=10.0)
        assert "error" not in completion_resp

        result = completion_resp.get("result") or {}
        items = result.get("items") if isinstance(result, dict) else result
        assert isinstance(items, list)
        labels = {item.get("label") for item in items if isinstance(item, dict)}
        assert "a" in labels
        assert "b" in labels
    finally:
        client.shutdown()


def test_lsp_server_outputs_fields_imported_field_definition_jumps_to_fragment(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    fragment_path = workspace / "frag.yaml"
    fragment_text = "\n".join(
        [
            "fields:",
            "  b:",
            '    compute: "1"',
            "",
        ]
    )
    fragment_path.write_text(fragment_text, encoding="utf-8")

    yaml_path = workspace / "demo.yaml"
    yaml_text = "\n".join(
        [
            "imports:",
            "  frags: ./frag.yaml",
            "name: demo",
            "main_source:",
            "  source_id: orders",
            "  loader: tests.fixtures.mock_loaders.mock_loader",
            "  fields: {a: {}}",
            "sources: {}",
            "fields:",
            "  $import: frags.fields",
            "outputs:",
            "  - name: out",
            "    to: {file: out.xlsx}",
            "    fields:",
            "      - a",
            "      - b",
            "",
        ]
    )
    yaml_path.write_text(yaml_text, encoding="utf-8")

    proc = _start_lsp_server_process(workspace)
    client = _LspClient(proc)
    try:
        init_id = client.send_request(
            "initialize",
            {
                "processId": None,
                "rootUri": workspace.as_uri(),
                "capabilities": {},
                "workspaceFolders": [{"uri": workspace.as_uri(), "name": "workspace"}],
            },
        )
        init_resp = client.recv_until(lambda msg: msg.get("id") == init_id, timeout=10.0)
        assert "error" not in init_resp

        client.send_notification("initialized", {})
        client.send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": yaml_path.as_uri(),
                    "languageId": "yaml",
                    "version": 1,
                    "text": yaml_text,
                }
            },
        )
        _ = client.recv_until(lambda msg: msg.get("method") == "textDocument/publishDiagnostics", timeout=10.0)

        lines = yaml_text.splitlines()
        out_fields_line = next(idx for idx, line in enumerate(lines) if line.strip() == "- b")
        cursor_char = int(lines[out_fields_line].index("b"))

        definition_id = client.send_request(
            "textDocument/definition",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": out_fields_line, "character": cursor_char},
            },
        )
        definition_resp = client.recv_until(lambda msg: msg.get("id") == definition_id, timeout=10.0)
        assert "error" not in definition_resp

        locations = definition_resp.get("result") or []
        assert isinstance(locations, list)
        assert any(loc.get("uri") == fragment_path.as_uri() for loc in locations)
    finally:
        client.shutdown()


def test_lsp_server_outputs_fields_yaml_alias_definition_and_hover(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    yaml_path = workspace / "demo.yaml"
    yaml_text = "\n".join(
        [
            "detail_fields: &detail_fields [a, b]",
            "name: demo",
            "main_source:",
            "  source_id: orders",
            "  loader: tests.fixtures.mock_loaders.mock_loader",
            "  fields: {a: {}, b: {}}",
            "sources: {}",
            "outputs:",
            "  - name: out",
            "    to: {file: out.xlsx}",
            "    fields:",
            "      - *detail_fields",
            "",
        ]
    )
    yaml_path.write_text(yaml_text, encoding="utf-8")

    proc = _start_lsp_server_process(workspace)
    client = _LspClient(proc)
    try:
        init_id = client.send_request(
            "initialize",
            {
                "processId": None,
                "rootUri": workspace.as_uri(),
                "capabilities": {},
                "workspaceFolders": [{"uri": workspace.as_uri(), "name": "workspace"}],
            },
        )
        init_resp = client.recv_until(lambda msg: msg.get("id") == init_id, timeout=10.0)
        assert "error" not in init_resp

        client.send_notification("initialized", {})
        client.send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": yaml_path.as_uri(),
                    "languageId": "yaml",
                    "version": 1,
                    "text": yaml_text,
                }
            },
        )
        _ = client.recv_until(lambda msg: msg.get("method") == "textDocument/publishDiagnostics", timeout=10.0)

        lines = yaml_text.splitlines()
        alias_line = next(idx for idx, line in enumerate(lines) if "*detail_fields" in line)
        cursor_char = int(lines[alias_line].index("detail_fields")) + 2

        definition_id = client.send_request(
            "textDocument/definition",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": alias_line, "character": cursor_char},
            },
        )
        definition_resp = client.recv_until(lambda msg: msg.get("id") == definition_id, timeout=10.0)
        assert "error" not in definition_resp

        locations = definition_resp.get("result") or []
        assert isinstance(locations, list)
        assert any(loc.get("uri") == yaml_path.as_uri() for loc in locations)

        hover_id = client.send_request(
            "textDocument/hover",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": alias_line, "character": cursor_char},
            },
        )
        hover_resp = client.recv_until(lambda msg: msg.get("id") == hover_id, timeout=10.0)
        assert "error" not in hover_resp
        hover = hover_resp.get("result") or {}
        value = (hover.get("contents") or {}).get("value") if isinstance(hover, dict) else ""
        assert isinstance(value, str)
        assert "YAML alias:" in value
        assert "preview:" in value
        assert "a" in value
        assert "b" in value
    finally:
        client.shutdown()


def test_lsp_server_expression_compute_definition_and_hover(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    yaml_path = workspace / "demo.yaml"
    yaml_text = "\n".join(
        [
            "name: demo",
            "main_source:",
            "  source_id: orders",
            "  loader: tests.fixtures.mock_loaders.mock_loader",
            "  fields:",
            "    a: {name: A}",
            "sources: {}",
            "fields:",
            "  sum:",
            '    compute: "a + 1"',
            "outputs: []",
            "",
        ]
    )
    yaml_path.write_text(yaml_text, encoding="utf-8")

    proc = _start_lsp_server_process(workspace)
    client = _LspClient(proc)
    try:
        init_id = client.send_request(
            "initialize",
            {
                "processId": None,
                "rootUri": workspace.as_uri(),
                "capabilities": {},
                "workspaceFolders": [{"uri": workspace.as_uri(), "name": "workspace"}],
            },
        )
        init_resp = client.recv_until(lambda msg: msg.get("id") == init_id, timeout=10.0)
        assert "error" not in init_resp

        client.send_notification("initialized", {})
        client.send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": yaml_path.as_uri(),
                    "languageId": "yaml",
                    "version": 1,
                    "text": yaml_text,
                }
            },
        )
        _ = client.recv_until(lambda msg: msg.get("method") == "textDocument/publishDiagnostics", timeout=10.0)

        lines = yaml_text.splitlines()
        expr_line = next(idx for idx, line in enumerate(lines) if 'compute: "a + 1"' in line)
        cursor_char = int(lines[expr_line].index('"a + 1"')) + 1

        definition_id = client.send_request(
            "textDocument/definition",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": expr_line, "character": cursor_char},
            },
        )
        definition_resp = client.recv_until(lambda msg: msg.get("id") == definition_id, timeout=10.0)
        assert "error" not in definition_resp
        locations = definition_resp.get("result") or []
        assert isinstance(locations, list)
        assert any(loc.get("uri") == yaml_path.as_uri() for loc in locations)

        expected_def_line = next(idx for idx, line in enumerate(lines) if line.strip() == "a: {name: A}")
        assert any(
            loc.get("uri") == yaml_path.as_uri() and (loc.get("range") or {}).get("start", {}).get("line") == expected_def_line
            for loc in locations
        )

        hover_id = client.send_request(
            "textDocument/hover",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": expr_line, "character": cursor_char},
            },
        )
        hover_resp = client.recv_until(lambda msg: msg.get("id") == hover_id, timeout=10.0)
        assert "error" not in hover_resp
        hover = hover_resp.get("result") or {}
        value = (hover.get("contents") or {}).get("value") if isinstance(hover, dict) else ""
        assert isinstance(value, str)
        assert "Field:" in value
        assert "scope:" in value
        assert "fields.*.compute" in value
    finally:
        client.shutdown()


def test_lsp_server_expression_definition_returns_multiple_locations_for_ambiguous_field_id(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    yaml_path = workspace / "demo.yaml"
    yaml_text = "\n".join(
        [
            "name: demo",
            "main_source:",
            "  source_id: orders",
            "  loader: tests.fixtures.mock_loaders.mock_loader",
            "  fields:",
            "    a: {name: A}",
            "sources: {}",
            "fields:",
            "  a:",
            '    compute: "1"',
            "  sum:",
            '    compute: "a + 1"',
            "outputs: []",
            "",
        ]
    )
    yaml_path.write_text(yaml_text, encoding="utf-8")

    proc = _start_lsp_server_process(workspace)
    client = _LspClient(proc)
    try:
        init_id = client.send_request(
            "initialize",
            {
                "processId": None,
                "rootUri": workspace.as_uri(),
                "capabilities": {},
                "workspaceFolders": [{"uri": workspace.as_uri(), "name": "workspace"}],
            },
        )
        init_resp = client.recv_until(lambda msg: msg.get("id") == init_id, timeout=10.0)
        assert "error" not in init_resp

        client.send_notification("initialized", {})
        client.send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": yaml_path.as_uri(),
                    "languageId": "yaml",
                    "version": 1,
                    "text": yaml_text,
                }
            },
        )
        _ = client.recv_until(lambda msg: msg.get("method") == "textDocument/publishDiagnostics", timeout=10.0)

        lines = yaml_text.splitlines()
        expr_line = next(idx for idx, line in enumerate(lines) if line.strip() == 'compute: "a + 1"')
        cursor_char = int(lines[expr_line].index('"a + 1"')) + 1

        definition_id = client.send_request(
            "textDocument/definition",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": expr_line, "character": cursor_char},
            },
        )
        definition_resp = client.recv_until(lambda msg: msg.get("id") == definition_id, timeout=10.0)
        assert "error" not in definition_resp

        locations = definition_resp.get("result") or []
        assert isinstance(locations, list)
        assert len(locations) >= 2

        main_a_line = next(idx for idx, line in enumerate(lines) if line.strip() == "a: {name: A}")
        derived_a_line = next(idx for idx, line in enumerate(lines) if line.strip() == "a:")
        got_lines = {
            (loc.get("range") or {}).get("start", {}).get("line")
            for loc in locations
            if isinstance(loc, dict) and loc.get("uri") == yaml_path.as_uri()
        }
        assert main_a_line in got_lines
        assert derived_a_line in got_lines
    finally:
        client.shutdown()


def test_lsp_server_expression_definition_returns_empty_for_unknown_token(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    yaml_path = workspace / "demo.yaml"
    yaml_text = "\n".join(
        [
            "name: demo",
            "main_source: {source_id: orders, loader: tests.fixtures.mock_loaders.mock_loader, fields: {a: {}}}",
            "sources: {}",
            "fields:",
            "  sum:",
            '    compute: "unknown + 1"',
            "outputs: []",
            "",
        ]
    )
    yaml_path.write_text(yaml_text, encoding="utf-8")

    proc = _start_lsp_server_process(workspace)
    client = _LspClient(proc)
    try:
        init_id = client.send_request(
            "initialize",
            {
                "processId": None,
                "rootUri": workspace.as_uri(),
                "capabilities": {},
                "workspaceFolders": [{"uri": workspace.as_uri(), "name": "workspace"}],
            },
        )
        init_resp = client.recv_until(lambda msg: msg.get("id") == init_id, timeout=10.0)
        assert "error" not in init_resp

        client.send_notification("initialized", {})
        client.send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": yaml_path.as_uri(),
                    "languageId": "yaml",
                    "version": 1,
                    "text": yaml_text,
                }
            },
        )
        _ = client.recv_until(lambda msg: msg.get("method") == "textDocument/publishDiagnostics", timeout=10.0)

        lines = yaml_text.splitlines()
        expr_line = next(idx for idx, line in enumerate(lines) if 'compute: "unknown + 1"' in line)
        cursor_char = int(lines[expr_line].index('"unknown + 1"')) + 1

        definition_id = client.send_request(
            "textDocument/definition",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": expr_line, "character": cursor_char},
            },
        )
        definition_resp = client.recv_until(lambda msg: msg.get("id") == definition_id, timeout=10.0)
        assert "error" not in definition_resp

        locations = definition_resp.get("result") or []
        assert locations == []
    finally:
        client.shutdown()


def test_lsp_server_expression_completion_in_aggregate_scope_is_restricted(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    yaml_path = workspace / "demo.yaml"
    yaml_text = "\n".join(
        [
            "name: demo",
            "main_source:",
            "  source_id: orders",
            "  loader: tests.fixtures.mock_loaders.mock_loader",
            "  fields: {a: {}, b: {}}",
            "sources: {}",
            "fields:",
            "  c:",
            '    compute: "a + 1"',
            "outputs:",
            "  - name: out",
            "    to: {file: out.xlsx}",
            "    aggregate:",
            "      group_by: [a]",
            "      fields:",
            "        cnt:",
            '          compute: "a + cnt"',
            "",
        ]
    )
    yaml_path.write_text(yaml_text, encoding="utf-8")

    proc = _start_lsp_server_process(workspace)
    client = _LspClient(proc)
    try:
        init_id = client.send_request(
            "initialize",
            {
                "processId": None,
                "rootUri": workspace.as_uri(),
                "capabilities": {},
                "workspaceFolders": [{"uri": workspace.as_uri(), "name": "workspace"}],
            },
        )
        init_resp = client.recv_until(lambda msg: msg.get("id") == init_id, timeout=10.0)
        assert "error" not in init_resp

        client.send_notification("initialized", {})
        client.send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": yaml_path.as_uri(),
                    "languageId": "yaml",
                    "version": 1,
                    "text": yaml_text,
                }
            },
        )
        _ = client.recv_until(lambda msg: msg.get("method") == "textDocument/publishDiagnostics", timeout=10.0)

        lines = yaml_text.splitlines()
        expr_line = next(idx for idx, line in enumerate(lines) if line.strip() == 'compute: "a + cnt"')
        cursor_char = int(lines[expr_line].index('"a + cnt"')) + 1

        completion_id = client.send_request(
            "textDocument/completion",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": expr_line, "character": cursor_char},
            },
        )
        completion_resp = client.recv_until(lambda msg: msg.get("id") == completion_id, timeout=10.0)
        assert "error" not in completion_resp

        result = completion_resp.get("result") or {}
        items = result.get("items") if isinstance(result, dict) else result
        assert isinstance(items, list)
        labels = {item.get("label") for item in items if isinstance(item, dict)}
        assert "a" in labels
        assert "cnt" in labels
        assert "b" not in labels
        assert "c" not in labels
    finally:
        client.shutdown()


def test_lsp_server_aggregate_group_by_empty_list_item_completion_works(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    yaml_path = workspace / "demo.yaml"
    yaml_text = "\n".join(
        [
            "name: demo",
            "main_source:",
            "  source_id: orders",
            "  loader: tests.fixtures.mock_loaders.mock_loader",
            "  fields: {a: {}, b: {}}",
            "sources: {}",
            "outputs:",
            "  - name: out",
            "    to: {file: out.xlsx}",
            "    aggregate:",
            "      group_by:",
            "        - ",
            "      fields:",
            "        cnt: {count: {}}",
            "",
        ]
    )
    yaml_path.write_text(yaml_text, encoding="utf-8")

    proc = _start_lsp_server_process(workspace)
    client = _LspClient(proc)
    try:
        init_id = client.send_request(
            "initialize",
            {
                "processId": None,
                "rootUri": workspace.as_uri(),
                "capabilities": {},
                "workspaceFolders": [{"uri": workspace.as_uri(), "name": "workspace"}],
            },
        )
        init_resp = client.recv_until(lambda msg: msg.get("id") == init_id, timeout=10.0)
        assert "error" not in init_resp

        client.send_notification("initialized", {})
        client.send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": yaml_path.as_uri(),
                    "languageId": "yaml",
                    "version": 1,
                    "text": yaml_text,
                }
            },
        )
        _ = client.recv_until(lambda msg: msg.get("method") == "textDocument/publishDiagnostics", timeout=10.0)

        lines = yaml_text.splitlines()
        empty_item_line = next(idx for idx, line in enumerate(lines) if line.strip() == "-")
        cursor_char = len(lines[empty_item_line])
        completion_id = client.send_request(
            "textDocument/completion",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": empty_item_line, "character": cursor_char},
            },
        )
        completion_resp = client.recv_until(lambda msg: msg.get("id") == completion_id, timeout=10.0)
        assert "error" not in completion_resp

        result = completion_resp.get("result") or {}
        items = result.get("items") if isinstance(result, dict) else result
        assert isinstance(items, list)
        labels = {item.get("label") for item in items if isinstance(item, dict)}
        assert "a" in labels
        assert "cnt" in labels
    finally:
        client.shutdown()


def test_lsp_server_aggregate_definition_orders_out_field_before_global_field(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    yaml_path = workspace / "demo.yaml"
    yaml_text = "\n".join(
        [
            "name: demo",
            "main_source:",
            "  source_id: orders",
            "  loader: tests.fixtures.mock_loaders.mock_loader",
            "  fields: {a: {}}",
            "sources: {}",
            "fields:",
            "  sum_amount:",
            '    compute: "a + 1"',
            "outputs:",
            "  - name: out",
            "    to: {file: out.xlsx}",
            "    aggregate:",
            "      group_by: [a]",
            "      fields:",
            "        sum_amount: {sum: {field: a}}",
            "        rank:",
            "          dense_rank:",
            "            by: sum_amount",
            "            order: desc",
            "",
        ]
    )
    yaml_path.write_text(yaml_text, encoding="utf-8")

    proc = _start_lsp_server_process(workspace)
    client = _LspClient(proc)
    try:
        init_id = client.send_request(
            "initialize",
            {
                "processId": None,
                "rootUri": workspace.as_uri(),
                "capabilities": {},
                "workspaceFolders": [{"uri": workspace.as_uri(), "name": "workspace"}],
            },
        )
        init_resp = client.recv_until(lambda msg: msg.get("id") == init_id, timeout=10.0)
        assert "error" not in init_resp

        client.send_notification("initialized", {})
        client.send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": yaml_path.as_uri(),
                    "languageId": "yaml",
                    "version": 1,
                    "text": yaml_text,
                }
            },
        )
        _ = client.recv_until(lambda msg: msg.get("method") == "textDocument/publishDiagnostics", timeout=10.0)

        lines = yaml_text.splitlines()
        by_line = next(idx for idx, line in enumerate(lines) if line.strip() == "by: sum_amount")
        cursor_char = int(lines[by_line].index("sum_amount")) + 1
        definition_id = client.send_request(
            "textDocument/definition",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": by_line, "character": cursor_char},
            },
        )
        definition_resp = client.recv_until(lambda msg: msg.get("id") == definition_id, timeout=10.0)
        assert "error" not in definition_resp

        locations = definition_resp.get("result") or []
        assert isinstance(locations, list)
        assert len(locations) >= 2

        out_field_line = next(idx for idx, line in enumerate(lines) if line.strip() == "sum_amount: {sum: {field: a}}")
        global_field_line = next(idx for idx, line in enumerate(lines) if line.strip() == "sum_amount:")
        assert locations[0].get("uri") == yaml_path.as_uri()
        assert locations[0].get("range", {}).get("start", {}).get("line") == out_field_line
        assert locations[1].get("uri") == yaml_path.as_uri()
        assert locations[1].get("range", {}).get("start", {}).get("line") == global_field_line
    finally:
        client.shutdown()


def test_lsp_server_aggregate_completion_definition_and_hover_work_for_ecommerce_report(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    repo_root = Path(__file__).resolve(strict=False).parents[2]
    src_yaml = (
        repo_root / "notebooks" / "marimo" / "demo_big_data_report" / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "ecommerce_report.yaml"
    )
    src_frag = (
        repo_root
        / "notebooks"
        / "marimo"
        / "demo_big_data_report"
        / "chapters_of_yaml_dsl"
        / "declared_yaml_dsl"
        / "ecommerce_report_fragments.yaml"
    )
    assert src_yaml.exists()
    assert src_frag.exists()

    yaml_text = src_yaml.read_text(encoding="utf-8")
    frag_text = src_frag.read_text(encoding="utf-8")
    yaml_path = workspace / "ecommerce_report.yaml"
    frag_path = workspace / "ecommerce_report_fragments.yaml"
    yaml_path.write_text(yaml_text, encoding="utf-8")
    frag_path.write_text(frag_text, encoding="utf-8")

    proc = _start_lsp_server_process(workspace)
    client = _LspClient(proc)
    try:
        init_id = client.send_request(
            "initialize",
            {
                "processId": None,
                "rootUri": workspace.as_uri(),
                "capabilities": {},
                "workspaceFolders": [{"uri": workspace.as_uri(), "name": "workspace"}],
            },
        )
        init_resp = client.recv_until(lambda msg: msg.get("id") == init_id, timeout=10.0)
        assert "error" not in init_resp

        client.send_notification("initialized", {})
        client.send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": yaml_path.as_uri(),
                    "languageId": "yaml",
                    "version": 1,
                    "text": yaml_text,
                }
            },
        )
        _ = client.recv_until(lambda msg: msg.get("method") == "textDocument/publishDiagnostics", timeout=10.0)

        lines = yaml_text.splitlines()
        by_line = next(idx for idx, line in enumerate(lines) if line.strip() == "by: sum_order_amount")
        token_char = int(lines[by_line].index("sum_order_amount"))

        completion_id = client.send_request(
            "textDocument/completion",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": by_line, "character": token_char},
            },
        )
        completion_resp = client.recv_until(lambda msg: msg.get("id") == completion_id, timeout=10.0)
        assert "error" not in completion_resp
        result = completion_resp.get("result") or {}
        items = result.get("items") if isinstance(result, dict) else result
        assert isinstance(items, list)
        labels = {item.get("label") for item in items if isinstance(item, dict)}
        assert "sum_order_amount" in labels
        assert "region_name_display" in labels

        sum_item = next(item for item in items if isinstance(item, dict) and item.get("label") == "sum_order_amount")
        assert "out_field_id" in str(sum_item.get("detail") or "")

        definition_id = client.send_request(
            "textDocument/definition",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": by_line, "character": token_char + 1},
            },
        )
        definition_resp = client.recv_until(lambda msg: msg.get("id") == definition_id, timeout=10.0)
        assert "error" not in definition_resp
        locations = definition_resp.get("result") or []
        assert isinstance(locations, list)
        assert locations

        expected_def_line = max(
            idx for idx, line in enumerate(lines) if idx < by_line and line.strip() == "sum_order_amount: {sum: {field: order_amount}}"
        )
        assert locations[0].get("uri") == yaml_path.as_uri()
        assert locations[0].get("range", {}).get("start", {}).get("line") == expected_def_line

        hover_id = client.send_request(
            "textDocument/hover",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": by_line, "character": token_char + 1},
            },
        )
        hover_resp = client.recv_until(lambda msg: msg.get("id") == hover_id, timeout=10.0)
        assert "error" not in hover_resp
        hover = hover_resp.get("result") or {}
        value = (hover.get("contents") or {}).get("value") or ""
        assert "Aggregate out_field_id: sum_order_amount" in str(value)
    finally:
        client.shutdown()


def test_lsp_server_call_by_kwargs_value_completion_definition_and_hover_work_for_ecommerce_report(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    repo_root = Path(__file__).resolve(strict=False).parents[2]
    src_yaml = (
        repo_root / "notebooks" / "marimo" / "demo_big_data_report" / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "ecommerce_report.yaml"
    )
    src_frag = (
        repo_root
        / "notebooks"
        / "marimo"
        / "demo_big_data_report"
        / "chapters_of_yaml_dsl"
        / "declared_yaml_dsl"
        / "ecommerce_report_fragments.yaml"
    )
    assert src_yaml.exists()
    assert src_frag.exists()

    yaml_text = src_yaml.read_text(encoding="utf-8")
    frag_text = src_frag.read_text(encoding="utf-8")
    yaml_path = workspace / "ecommerce_report.yaml"
    frag_path = workspace / "ecommerce_report_fragments.yaml"
    yaml_path.write_text(yaml_text, encoding="utf-8")
    frag_path.write_text(frag_text, encoding="utf-8")

    proc = _start_lsp_server_process(workspace)
    client = _LspClient(proc)
    try:
        init_id = client.send_request(
            "initialize",
            {
                "processId": None,
                "rootUri": workspace.as_uri(),
                "capabilities": {},
                "workspaceFolders": [{"uri": workspace.as_uri(), "name": "workspace"}],
            },
        )
        init_resp = client.recv_until(lambda msg: msg.get("id") == init_id, timeout=10.0)
        assert "error" not in init_resp

        client.send_notification("initialized", {})
        client.send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": yaml_path.as_uri(),
                    "languageId": "yaml",
                    "version": 1,
                    "text": yaml_text,
                }
            },
        )
        _ = client.recv_until(lambda msg: msg.get("method") == "textDocument/publishDiagnostics", timeout=10.0)

        lines = yaml_text.splitlines()
        call_by_line = next(idx for idx, line in enumerate(lines) if "calc_profit(" in line and "order_amount=order_amount" in line)
        lhs_char = int(lines[call_by_line].index("order_amount"))
        rhs_char = int(lines[call_by_line].index("order_amount=order_amount")) + len("order_amount=")

        completion_id = client.send_request(
            "textDocument/completion",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": call_by_line, "character": rhs_char},
            },
        )
        completion_resp = client.recv_until(lambda msg: msg.get("id") == completion_id, timeout=10.0)
        assert "error" not in completion_resp
        result = completion_resp.get("result") or {}
        items = result.get("items") if isinstance(result, dict) else result
        assert isinstance(items, list)
        labels = {item.get("label") for item in items if isinstance(item, dict)}
        assert "order_amount" in labels
        assert "product_cost" in labels

        definition_id = client.send_request(
            "textDocument/definition",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": call_by_line, "character": rhs_char},
            },
        )
        definition_resp = client.recv_until(lambda msg: msg.get("id") == definition_id, timeout=10.0)
        assert "error" not in definition_resp
        locations = definition_resp.get("result") or []
        assert isinstance(locations, list)
        assert locations
        expected_field_line = next(idx for idx, line in enumerate(lines) if line.strip().startswith("order_amount:"))
        assert any(
            loc.get("uri") == yaml_path.as_uri() and loc.get("range", {}).get("start", {}).get("line") == expected_field_line
            for loc in locations
        )

        hover_id = client.send_request(
            "textDocument/hover",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": call_by_line, "character": rhs_char},
            },
        )
        hover_resp = client.recv_until(lambda msg: msg.get("id") == hover_id, timeout=10.0)
        assert "error" not in hover_resp
        hover = hover_resp.get("result") or {}
        value = (hover.get("contents") or {}).get("value") or ""
        assert "order_amount" in str(value)

        lhs_def_id = client.send_request(
            "textDocument/definition",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": call_by_line, "character": lhs_char + 1},
            },
        )
        lhs_def_resp = client.recv_until(lambda msg: msg.get("id") == lhs_def_id, timeout=10.0)
        assert "error" not in lhs_def_resp
        lhs_locations = lhs_def_resp.get("result")
        assert not lhs_locations
    finally:
        client.shutdown()


def test_lsp_server_call_by_kwargs_value_completion_supports_empty_value(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    (workspace / "mymod.py").write_text("def fn(**_kwargs):\n    return 1\n", encoding="utf-8")

    yaml_path = workspace / "demo.yaml"
    yaml_text = "\n".join(
        [
            "name: demo",
            "main_source: {source_id: orders, loader: scalim_misc.demo_big_data_report.loaders:load_orders, fields: {order_amount: {}}}",
            "sources: {}",
            "fields:",
            "  profit:",
            '    call_by: "mymod:fn(order_amount=)"',
            "",
        ]
    )
    yaml_path.write_text(yaml_text, encoding="utf-8")

    proc = _start_lsp_server_process(workspace)
    client = _LspClient(proc)
    try:
        init_id = client.send_request(
            "initialize",
            {
                "processId": None,
                "rootUri": workspace.as_uri(),
                "capabilities": {},
                "workspaceFolders": [{"uri": workspace.as_uri(), "name": "workspace"}],
            },
        )
        init_resp = client.recv_until(lambda msg: msg.get("id") == init_id, timeout=10.0)
        assert "error" not in init_resp

        client.send_notification("initialized", {})
        client.send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": yaml_path.as_uri(),
                    "languageId": "yaml",
                    "version": 1,
                    "text": yaml_text,
                }
            },
        )
        _ = client.recv_until(lambda msg: msg.get("method") == "textDocument/publishDiagnostics", timeout=10.0)

        lines = yaml_text.splitlines()
        line0 = next(idx for idx, line in enumerate(lines) if "order_amount=" in line)
        char0 = int(lines[line0].index("order_amount=")) + len("order_amount=")
        completion_id = client.send_request(
            "textDocument/completion",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": line0, "character": char0},
            },
        )
        completion_resp = client.recv_until(lambda msg: msg.get("id") == completion_id, timeout=10.0)
        assert "error" not in completion_resp
        result = completion_resp.get("result") or {}
        items = result.get("items") if isinstance(result, dict) else result
        assert isinstance(items, list)
        labels = {item.get("label") for item in items if isinstance(item, dict)}
        assert labels
        assert "order_amount" in labels
    finally:
        client.shutdown()


def test_lsp_server_aggregate_call_by_prefers_out_field_id_definition(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    yaml_path = workspace / "demo.yaml"
    yaml_text = "\n".join(
        [
            "name: demo",
            "main_source: {source_id: orders, loader: scalim_misc.demo_big_data_report.loaders:load_orders, fields: {order_amount: {}}}",
            "sources: {}",
            "outputs:",
            "  - name: out",
            "    to: {file: out.xlsx}",
            "    aggregate:",
            "      group_by: [order_amount]",
            "      fields:",
            "        sum_amount: {sum: {field: order_amount}}",
            "        score:",
            '          call_by: "^score_by_rank(rank=sum_amount, base=100, step=3)"',
            "",
        ]
    )
    yaml_path.write_text(yaml_text, encoding="utf-8")

    proc = _start_lsp_server_process(workspace)
    client = _LspClient(proc)
    try:
        init_id = client.send_request(
            "initialize",
            {
                "processId": None,
                "rootUri": workspace.as_uri(),
                "capabilities": {},
                "workspaceFolders": [{"uri": workspace.as_uri(), "name": "workspace"}],
            },
        )
        init_resp = client.recv_until(lambda msg: msg.get("id") == init_id, timeout=10.0)
        assert "error" not in init_resp

        client.send_notification("initialized", {})
        client.send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": yaml_path.as_uri(),
                    "languageId": "yaml",
                    "version": 1,
                    "text": yaml_text,
                }
            },
        )
        _ = client.recv_until(lambda msg: msg.get("method") == "textDocument/publishDiagnostics", timeout=10.0)

        lines = yaml_text.splitlines()
        call_by_line = next(idx for idx, line in enumerate(lines) if "rank=sum_amount" in line)
        rhs_char = int(lines[call_by_line].index("sum_amount")) + 1

        definition_id = client.send_request(
            "textDocument/definition",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": call_by_line, "character": rhs_char},
            },
        )
        definition_resp = client.recv_until(lambda msg: msg.get("id") == definition_id, timeout=10.0)
        assert "error" not in definition_resp
        locations = definition_resp.get("result") or []
        assert isinstance(locations, list)
        assert locations

        out_field_line = next(idx for idx, line in enumerate(lines) if line.strip() == "sum_amount: {sum: {field: order_amount}}")
        assert locations[0].get("uri") == yaml_path.as_uri()
        assert locations[0].get("range", {}).get("start", {}).get("line") == out_field_line
    finally:
        client.shutdown()


def test_lsp_server_imports_path_definition_completion_and_preset_definition(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    fragments_dir = workspace / "fragments"
    fragments_dir.mkdir()
    fragment_path = fragments_dir / "common.yaml"
    fragment_path.write_text("x: 1\n", encoding="utf-8")

    (workspace / "scalim.yaml").write_text(
        "\n".join(
            [
                "yaml_dsl:",
                "  import_roots:",
                "    - path: .",
                '      alias: "@"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    yaml_path = workspace / "demo.yaml"
    yaml_text = "\n".join(
        [
            "imports:",
            '  common: "@/fragments/common.yaml"',
            "  preset: scalim://yaml-dsl/presets/common.yaml",
            "name: demo",
            "",
        ]
    )
    yaml_path.write_text(yaml_text, encoding="utf-8")

    proc = _start_lsp_server_process(workspace)
    client = _LspClient(proc)
    try:
        init_id = client.send_request(
            "initialize",
            {
                "processId": None,
                "rootUri": workspace.as_uri(),
                "capabilities": {},
                "workspaceFolders": [{"uri": workspace.as_uri(), "name": "workspace"}],
            },
        )
        init_resp = client.recv_until(lambda msg: msg.get("id") == init_id, timeout=10.0)
        assert "error" not in init_resp

        client.send_notification("initialized", {})
        client.send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": yaml_path.as_uri(),
                    "languageId": "yaml",
                    "version": 1,
                    "text": yaml_text,
                }
            },
        )
        _ = client.recv_until(lambda msg: msg.get("method") == "textDocument/publishDiagnostics", timeout=10.0)

        # imports.common path completion
        import_line_idx = next(i for i, line in enumerate(yaml_text.splitlines()) if "common:" in line)
        import_line = yaml_text.splitlines()[import_line_idx]
        cursor_char = int(import_line.index("common.yaml")) + len("co")
        completion_id = client.send_request(
            "textDocument/completion",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": import_line_idx, "character": cursor_char},
            },
        )
        completion_resp = client.recv_until(lambda msg: msg.get("id") == completion_id, timeout=10.0)
        assert "error" not in completion_resp
        items = completion_resp.get("result", {}).get("items", [])
        labels = {item.get("label") for item in items}
        assert "fragments/common.yaml" in labels

        # imports.common definition -> fragment file
        cursor_char = int(import_line.index("fragments")) + 2
        definition_id = client.send_request(
            "textDocument/definition",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": import_line_idx, "character": cursor_char},
            },
        )
        definition_resp = client.recv_until(lambda msg: msg.get("id") == definition_id, timeout=10.0)
        assert "error" not in definition_resp
        locations = definition_resp.get("result") or []
        assert any(loc.get("uri") == fragment_path.as_uri() for loc in locations)

        # imports.preset definition -> virtual document uri
        preset_line_idx = next(i for i, line in enumerate(yaml_text.splitlines()) if "preset:" in line)
        preset_line = yaml_text.splitlines()[preset_line_idx]
        preset_char = int(preset_line.index("scalim://")) + 2
        preset_def_id = client.send_request(
            "textDocument/definition",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": preset_line_idx, "character": preset_char},
            },
        )
        preset_def_resp = client.recv_until(lambda msg: msg.get("id") == preset_def_id, timeout=10.0)
        assert "error" not in preset_def_resp
        preset_locations = preset_def_resp.get("result") or []
        assert any(str(loc.get("uri") or "").startswith("scalim-preset:///yaml-dsl/presets/") for loc in preset_locations)

        # executeCommand -> preset text
        cmd_id = client.send_request(
            "workspace/executeCommand",
            {"command": "scalim.preset.getText", "arguments": ["yaml-dsl/presets/common.yaml"]},
        )
        cmd_resp = client.recv_until(lambda msg: msg.get("id") == cmd_id, timeout=10.0)
        assert "error" not in cmd_resp
        payload = cmd_resp.get("result") or {}
        assert payload.get("ok") is True
        assert "demo:" in str(payload.get("content") or "")

        # imports.<alias> empty value completion (cursor right after `:`)
        yaml_text_empty = "\n".join(
            [
                "imports:",
                "  common: ",
                "  preset: scalim://yaml-dsl/presets/common.yaml",
                "name: demo",
                "",
            ]
        )
        client.send_notification(
            "textDocument/didChange",
            {
                "textDocument": {"uri": yaml_path.as_uri(), "version": 2},
                "contentChanges": [{"text": yaml_text_empty}],
            },
        )

        empty_common_line_idx = next(i for i, line in enumerate(yaml_text_empty.splitlines()) if "common:" in line)
        empty_common_line = yaml_text_empty.splitlines()[empty_common_line_idx]
        cursor_char = int(empty_common_line.index(":")) + 1  # right after `:`, before trailing whitespace
        completion_id = client.send_request(
            "textDocument/completion",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": empty_common_line_idx, "character": cursor_char},
            },
        )
        completion_resp = client.recv_until(lambda msg: msg.get("id") == completion_id, timeout=10.0)
        assert "error" not in completion_resp
        empty_items = completion_resp.get("result", {}).get("items", [])
        empty_labels = {item.get("label") for item in empty_items}
        assert "./" in empty_labels
        assert "../" in empty_labels
        assert "@/" in empty_labels
    finally:
        client.shutdown()


def test_lsp_server_yaml_import_ref_completion_alias_and_fragment_keys(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    fragment_path = workspace / "frag.yaml"
    fragment_path.write_text(
        "\n".join(
            [
                "main_source_params:",
                "  order_ids: []",
                "fields:",
                "  a: {compute: '1'}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    yaml_path = workspace / "demo.yaml"
    yaml_text = "\n".join(
        [
            "imports:",
            "  fragments: ./frag.yaml",
            "name: demo",
            "main_source:",
            "  source_id: orders",
            "  loader: tests.fixtures.mock_loaders.mock_loader",
            "  params:",
            "    $import: ",
            "sources: {}",
            "fields: {}",
            "outputs: []",
            "",
        ]
    )
    yaml_path.write_text(yaml_text, encoding="utf-8")

    proc = _start_lsp_server_process(workspace)
    client = _LspClient(proc)
    try:
        init_id = client.send_request(
            "initialize",
            {
                "processId": None,
                "rootUri": workspace.as_uri(),
                "capabilities": {},
                "workspaceFolders": [{"uri": workspace.as_uri(), "name": "workspace"}],
            },
        )
        init_resp = client.recv_until(lambda msg: msg.get("id") == init_id, timeout=10.0)
        assert "error" not in init_resp

        client.send_notification("initialized", {})
        client.send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": yaml_path.as_uri(),
                    "languageId": "yaml",
                    "version": 1,
                    "text": yaml_text,
                }
            },
        )
        _ = client.recv_until(lambda msg: msg.get("method") == "textDocument/publishDiagnostics", timeout=10.0)

        # $import empty value -> alias completion
        lines = yaml_text.splitlines()
        import_line_idx = next(idx for idx, line in enumerate(lines) if line.strip().startswith("$import:"))
        import_line = lines[import_line_idx]
        cursor_char = int(import_line.index(":")) + 1
        completion_id = client.send_request(
            "textDocument/completion",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": import_line_idx, "character": cursor_char},
            },
        )
        completion_resp = client.recv_until(lambda msg: msg.get("id") == completion_id, timeout=10.0)
        assert "error" not in completion_resp
        items = completion_resp.get("result", {}).get("items", [])
        labels = {item.get("label") for item in items}
        assert "fragments." in labels

        # $import fragments. -> fragment key completion
        yaml_text2 = yaml_text.replace("    $import: ", "    $import: fragments.")
        client.send_notification(
            "textDocument/didChange",
            {
                "textDocument": {"uri": yaml_path.as_uri(), "version": 2},
                "contentChanges": [{"text": yaml_text2}],
            },
        )
        lines2 = yaml_text2.splitlines()
        import_line_idx2 = next(idx for idx, line in enumerate(lines2) if line.strip().startswith("$import:"))
        import_line2 = lines2[import_line_idx2]
        cursor_char2 = len(import_line2)

        completion_id2 = client.send_request(
            "textDocument/completion",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": import_line_idx2, "character": cursor_char2},
            },
        )
        completion_resp2 = client.recv_until(lambda msg: msg.get("id") == completion_id2, timeout=10.0)
        assert "error" not in completion_resp2
        items2 = completion_resp2.get("result", {}).get("items", [])
        labels2 = {item.get("label") for item in items2}
        assert "fragments.main_source_params" in labels2
        assert "fragments.fields" in labels2
    finally:
        client.shutdown()


def test_lsp_server_yaml_entity_definition_hover_and_completion(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    yaml_path = workspace / "demo.yaml"
    yaml_text = "\n".join(
        [
            "name: demo",
            "main_source:",
            "  source_id: orders",
            "  loader: tests.fixtures.mock_loaders.mock_loader",
            "  fields:",
            "    customer_id: {name: Customer ID}",
            "sources:",
            "  customers:",
            "    loader: tests.fixtures.mock_loaders.mock_loader",
            "    key: customer_id",
            "    fields:",
            "      customer_id: {name: Customer ID}",
            "relations:",
            "  orders_to_customers:",
            "    steps:",
            "      - from: orders.customer_id",
            "        to: customers.customer_id",
            "outputs: []",
            "",
        ]
    )
    yaml_path.write_text(yaml_text, encoding="utf-8")

    proc = _start_lsp_server_process(workspace)
    client = _LspClient(proc)
    try:
        init_id = client.send_request(
            "initialize",
            {
                "processId": None,
                "rootUri": workspace.as_uri(),
                "capabilities": {},
                "workspaceFolders": [{"uri": workspace.as_uri(), "name": "workspace"}],
            },
        )
        init_resp = client.recv_until(lambda msg: msg.get("id") == init_id, timeout=10.0)
        assert "error" not in init_resp

        client.send_notification("initialized", {})
        client.send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": yaml_path.as_uri(),
                    "languageId": "yaml",
                    "version": 1,
                    "text": yaml_text,
                }
            },
        )
        _ = client.recv_until(lambda msg: msg.get("method") == "textDocument/publishDiagnostics", timeout=10.0)

        lines = yaml_text.splitlines()
        from_line = next(i for i, line in enumerate(lines) if "from:" in line)
        from_text = lines[from_line]

        # definition on source_id segment -> main_source.source_id key location
        src_char = int(from_text.index("orders")) + 2
        def_src_id = client.send_request(
            "textDocument/definition",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": from_line, "character": src_char},
            },
        )
        def_src_resp = client.recv_until(lambda msg: msg.get("id") == def_src_id, timeout=10.0)
        assert "error" not in def_src_resp

        locations = def_src_resp.get("result") or []
        assert any(loc.get("uri") == yaml_path.as_uri() and loc.get("range", {}).get("start", {}).get("line") == 2 for loc in locations)

        # definition on field_id segment -> main_source.fields.customer_id key location
        field_char = int(from_text.index("customer_id")) + 2
        def_field_id = client.send_request(
            "textDocument/definition",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": from_line, "character": field_char},
            },
        )
        def_field_resp = client.recv_until(lambda msg: msg.get("id") == def_field_id, timeout=10.0)
        assert "error" not in def_field_resp
        field_locations = def_field_resp.get("result") or []
        assert any(
            loc.get("uri") == yaml_path.as_uri() and loc.get("range", {}).get("start", {}).get("line") == 5 for loc in field_locations
        )

        # hover on source_id segment
        hover_id = client.send_request(
            "textDocument/hover",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": from_line, "character": src_char},
            },
        )
        hover_resp = client.recv_until(lambda msg: msg.get("id") == hover_id, timeout=10.0)
        assert "error" not in hover_resp
        hover = hover_resp.get("result") or {}
        value = (hover.get("contents") or {}).get("value") if isinstance(hover, dict) else ""
        assert isinstance(value, str)
        assert "Source: orders" in value

        # completion after dot -> field ids
        from_line_text = lines[from_line]
        dot_char = int(from_line_text.index("orders.")) + len("orders.")
        completion_id = client.send_request(
            "textDocument/completion",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": from_line, "character": dot_char},
            },
        )
        completion_resp = client.recv_until(lambda msg: msg.get("id") == completion_id, timeout=10.0)
        assert "error" not in completion_resp
        items = completion_resp.get("result", {}).get("items", [])
        labels = {item.get("label") for item in items}
        assert "customer_id" in labels
    finally:
        client.shutdown()


def test_lsp_server_yaml_entity_unknown_id_publishes_hint_diagnostic(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    yaml_path = workspace / "demo.yaml"
    yaml_text = "\n".join(
        [
            "name: demo",
            "main_source:",
            "  source_id: orders",
            "  loader: tests.fixtures.mock_loaders.mock_loader",
            "  fields: {customer_id: {}}",
            "sources: {}",
            "relations:",
            "  r1:",
            "    steps:",
            "      - from: not_exist.customer_id",
            "        to: orders.customer_id",
            "outputs: []",
            "",
        ]
    )
    yaml_path.write_text(yaml_text, encoding="utf-8")

    proc = _start_lsp_server_process(workspace)
    client = _LspClient(proc)
    try:
        init_id = client.send_request(
            "initialize",
            {
                "processId": None,
                "rootUri": workspace.as_uri(),
                "capabilities": {},
                "workspaceFolders": [{"uri": workspace.as_uri(), "name": "workspace"}],
            },
        )
        init_resp = client.recv_until(lambda msg: msg.get("id") == init_id, timeout=10.0)
        assert "error" not in init_resp

        client.send_notification("initialized", {})
        client.send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": yaml_path.as_uri(),
                    "languageId": "yaml",
                    "version": 1,
                    "text": yaml_text,
                }
            },
        )
        _ = client.recv_until(lambda msg: msg.get("method") == "textDocument/publishDiagnostics", timeout=10.0)

        lines = yaml_text.splitlines()
        from_line = next(i for i, line in enumerate(lines) if "from:" in line)
        from_text = lines[from_line]
        cursor_char = int(from_text.index("not_exist")) + 2

        definition_id = client.send_request(
            "textDocument/definition",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": from_line, "character": cursor_char},
            },
        )
        definition_resp = client.recv_until(lambda msg: msg.get("id") == definition_id, timeout=10.0)
        assert "error" not in definition_resp
        assert not definition_resp.get("result")

        pub = client.recv_until(
            lambda msg: (
                msg.get("method") == "textDocument/publishDiagnostics"
                and any(d.get("code") == "scalim_unknown_entity_id" for d in msg.get("params", {}).get("diagnostics", []))
            ),
            timeout=10.0,
        )
        diags = pub.get("params", {}).get("diagnostics", [])
        assert any("Unknown source id" in str(d.get("message") or "") for d in diags)
    finally:
        client.shutdown()


def test_lsp_server_yaml_entity_workflow_run_definition(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    yaml_path = workspace / "workflow.yaml"
    yaml_text = "\n".join(
        [
            "workflow:",
            "  runs:",
            "    - id: extract",
            "      demand: x.yaml",
            "    - id: transform",
            "      depends_on: [extract]",
            "      demand: y.yaml",
            "",
        ]
    )
    yaml_path.write_text(yaml_text, encoding="utf-8")

    proc = _start_lsp_server_process(workspace)
    client = _LspClient(proc)
    try:
        init_id = client.send_request(
            "initialize",
            {
                "processId": None,
                "rootUri": workspace.as_uri(),
                "capabilities": {},
                "workspaceFolders": [{"uri": workspace.as_uri(), "name": "workspace"}],
            },
        )
        init_resp = client.recv_until(lambda msg: msg.get("id") == init_id, timeout=10.0)
        assert "error" not in init_resp

        client.send_notification("initialized", {})
        client.send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": yaml_path.as_uri(),
                    "languageId": "yaml",
                    "version": 1,
                    "text": yaml_text,
                }
            },
        )
        _ = client.recv_until(lambda msg: msg.get("method") == "textDocument/publishDiagnostics", timeout=10.0)

        depends_line = next(i for i, line in enumerate(yaml_text.splitlines()) if "depends_on:" in line)
        depends_text = yaml_text.splitlines()[depends_line]
        cursor_char = int(depends_text.index("extract")) + 2

        definition_id = client.send_request(
            "textDocument/definition",
            {
                "textDocument": {"uri": yaml_path.as_uri()},
                "position": {"line": depends_line, "character": cursor_char},
            },
        )
        definition_resp = client.recv_until(lambda msg: msg.get("id") == definition_id, timeout=10.0)
        assert "error" not in definition_resp
        locations = definition_resp.get("result") or []
        assert any(loc.get("uri") == yaml_path.as_uri() and loc.get("range", {}).get("start", {}).get("line") == 2 for loc in locations)
    finally:
        client.shutdown()


def _start_lsp_server_process(workspace: Path) -> subprocess.Popen[bytes]:
    code = "from scalim_yaml_dsl_lsp.cli import main; raise SystemExit(main(['serve', '--log-level', 'ERROR']))"
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    return subprocess.Popen(  # noqa: S603
        [sys.executable, "-c", code],
        cwd=str(workspace),
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )


def _encode_lsp_message(payload: Dict[str, Any]) -> bytes:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    header = "Content-Length: {}\r\n\r\n".format(len(body)).encode("ascii")
    return header + body


def _read_lsp_message(stream) -> Optional[Dict[str, Any]]:
    headers: Dict[str, str] = {}
    while True:
        line = stream.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        key, _, value = line.decode("ascii", errors="replace").partition(":")
        headers[key.strip().lower()] = value.strip()

    content_length_raw = headers.get("content-length", "")
    if not content_length_raw.isdigit():
        return None
    length = int(content_length_raw)
    body = b""
    while len(body) < length:
        chunk = stream.read(length - len(body))
        if not chunk:
            return None
        body += chunk

    return json.loads(body.decode("utf-8"))


class _LspClient:
    def __init__(self, proc: subprocess.Popen[bytes]) -> None:
        if proc.stdin is None or proc.stdout is None or proc.stderr is None:
            raise RuntimeError("unexpected: subprocess pipes not available")
        self._proc = proc
        self._stdin = proc.stdin
        self._stdout = proc.stdout
        self._stderr = proc.stderr
        self._inbox: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self._stash: List[Dict[str, Any]] = []
        self._next_id = 1
        self._stderr_lines: List[str] = []

        self._stdout_thread = threading.Thread(target=self._stdout_loop, daemon=True)
        self._stderr_thread = threading.Thread(target=self._stderr_loop, daemon=True)
        self._stdout_thread.start()
        self._stderr_thread.start()

    def send_request(self, method: str, params: Dict[str, Any]) -> int:
        msg_id = int(self._next_id)
        self._next_id += 1
        self._send({"jsonrpc": "2.0", "id": msg_id, "method": str(method), "params": params})
        return msg_id

    def send_notification(self, method: str, params: Dict[str, Any]) -> None:
        self._send({"jsonrpc": "2.0", "method": str(method), "params": params})

    def recv_until(self, predicate: Callable[[Dict[str, Any]], bool], *, timeout: float) -> Dict[str, Any]:
        end = time.monotonic() + float(timeout)
        for idx, item in enumerate(list(self._stash)):
            if predicate(item):
                return self._stash.pop(idx)

        while time.monotonic() < end:
            remaining = end - time.monotonic()
            try:
                msg = self._inbox.get(timeout=max(remaining, 0.01))
            except queue.Empty:
                continue
            if predicate(msg):
                return msg
            self._stash.append(msg)

        raise AssertionError("timeout waiting for LSP message; stderr:\n{}".format("".join(self._stderr_lines[-50:])))

    def shutdown(self) -> None:
        if self._proc.poll() is not None:
            return

        try:
            shutdown_id = self.send_request("shutdown", {})
            _ = self.recv_until(lambda msg: msg.get("id") == shutdown_id, timeout=5.0)
            self.send_notification("exit", {})
            self._stdin.close()
            self._proc.wait(timeout=5.0)
        except Exception:  # noqa: BLE001
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                self._proc.kill()

    def _send(self, msg: Dict[str, Any]) -> None:
        payload = _encode_lsp_message(msg)
        self._stdin.write(payload)
        self._stdin.flush()

    def _stdout_loop(self) -> None:
        while True:
            msg = _read_lsp_message(self._stdout)
            if msg is None:
                return
            self._inbox.put(msg)

    def _stderr_loop(self) -> None:
        while True:
            line = self._stderr.readline()
            if not line:
                return
            self._stderr_lines.append(line.decode("utf-8", errors="replace"))
