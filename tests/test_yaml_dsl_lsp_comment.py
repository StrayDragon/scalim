import argparse
import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

import scalim.cli.yaml_dsl as yaml_dsl
from scalim.cli import yaml_dsl_lsp


def _upsert_args(*paths: Path, schema_type: str = "demand", schema_path: str = "http://localhost:62831") -> argparse.Namespace:
    return argparse.Namespace(
        schema_type=schema_type,
        schema_path=schema_path,
        paths=list(paths),
    )


def test_upsert_lsp_comment_inserts_intellij_modeline(tmp_path) -> None:
    yaml_path = tmp_path / "demo.yaml"
    yaml_path.write_text("name: demo\n", encoding="utf-8")

    code = yaml_dsl._run_upsert_lsp_comment(_upsert_args(yaml_path))
    assert code == 0

    first_line = yaml_path.read_text(encoding="utf-8").splitlines()[0]
    assert first_line == "# $schema: http://localhost:62831/demand.gen.json"


def test_upsert_lsp_comment_upgrades_yaml_language_server_modeline_and_is_idempotent(tmp_path) -> None:
    yaml_path = tmp_path / "legacy.yaml"
    yaml_path.write_text(
        "# yaml-language-server: $schema=/wrong/path/demand.gen.json\nname: demo\n",
        encoding="utf-8",
    )

    code = yaml_dsl._run_upsert_lsp_comment(_upsert_args(yaml_path))
    assert code == 0

    content = yaml_path.read_text(encoding="utf-8")
    assert content.splitlines()[0] == "# $schema: http://localhost:62831/demand.gen.json"
    assert "yaml-language-server" not in content

    code = yaml_dsl._run_upsert_lsp_comment(_upsert_args(yaml_path))
    assert code == 0
    assert yaml_path.read_text(encoding="utf-8") == content


def test_upsert_lsp_comment_inserts_before_document_start_marker(tmp_path) -> None:
    yaml_path = tmp_path / "doc.yaml"
    yaml_path.write_text("---\nname: demo\n", encoding="utf-8")

    code = yaml_dsl._run_upsert_lsp_comment(_upsert_args(yaml_path))
    assert code == 0

    lines = yaml_path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "# $schema: http://localhost:62831/demand.gen.json"
    assert lines[2] == "---"


def test_resolve_schema_ref_supports_url_base_dir_base_and_full_json(tmp_path) -> None:
    assert yaml_dsl_lsp.resolve_schema_ref("workflow", "http://localhost:62831") == "http://localhost:62831/workflow.gen.json"

    base_dir = tmp_path / "schema"
    assert yaml_dsl_lsp.resolve_schema_ref("demand", str(base_dir)) == str(base_dir / "demand.gen.json")

    assert yaml_dsl_lsp.resolve_schema_ref("demand", "http://example.invalid/custom.json") == "http://example.invalid/custom.json"


def test_schema_serve_serves_schema_and_blocks_traversal() -> None:
    server, port, schema_filenames = yaml_dsl_lsp.create_schema_http_server(host="127.0.0.1", port=0)

    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()

    try:
        assert "demand.gen.json" in schema_filenames
        with urlopen("http://127.0.0.1:{}/demand.gen.json".format(port)) as res:
            assert res.getcode() == 200
            payload = json.loads(res.read().decode("utf-8"))
            assert isinstance(payload, dict)

        with urlopen("http://127.0.0.1:{}/..%2Fpyproject.toml".format(port)) as _res:
            raise AssertionError("expected traversal to be blocked")
    except HTTPError as exc:
        assert exc.code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
