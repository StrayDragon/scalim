from typing import Any, Dict, List

import scalim_cli.log as log_cli


def _collect(lines: List[str]) -> List[Dict[str, Any]]:
    return list(log_cli._iter_json_objects(lines))  # noqa: SLF001


def test_log_cli_parses_compact_profile_and_normalizes_keys() -> None:
    lines = [
        "noise line\n",
        '{"ts": 1.0, "lvl": 20, "lg": "scalim.performance", "msg": "x", "k": "performance.summary", "ctx": {"rid": "run_1", "dem": "demo"}, "f": {"tds": 0.2}}\n',
        "more noise\n",
    ]
    records = _collect(lines)
    assert len(records) == 1
    rec = records[0]
    assert rec["timestamp"] == 1.0
    assert rec["level"] == 20
    assert rec["logger"] == "scalim.performance"
    assert rec["message"] == "x"
    assert rec["kind"] == "performance.summary"
    assert rec["context"]["run_id"] == "run_1"
    assert rec["context"]["demand"] == "demo"
    assert rec["fields"]["total_duration_s"] == 0.2


def test_log_cli_recovers_multiline_json_object() -> None:
    lines = [
        "{\n",
        '  "ts": 2.0,\n',
        '  "lvl": 30,\n',
        '  "lg": "scalim.relations",\n',
        '  "msg": "y",\n',
        '  "k": "relations.summary"\n',
        "}\n",
    ]
    records = _collect(lines)
    assert len(records) == 1
    assert records[0]["timestamp"] == 2.0
    assert records[0]["kind"] == "relations.summary"
