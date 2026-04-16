from scalim.sinks.memory import InMemoryColumnSink


def test_inmemory_column_sink_get_rows_skips_missing_cells_and_2d_list_has_no_header() -> None:
    sink = InMemoryColumnSink()
    sink.write_batch([{"id": 1}, {"id": 2, "name": "B"}])

    rows = sink.get_rows()
    assert rows[0] == {"id": 1}
    assert rows[1]["name"] == "B"

    grid = sink.get_2d_list()
    assert grid[0] == [1, None]
    assert grid[1] == [2, "B"]
