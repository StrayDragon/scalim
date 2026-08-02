import pytest

from scalim.execution import ExecutionRequest, ExportLayout, OutputSpec
from scalim.sinks.memory import InMemoryRowDataSink


def test_execution_request_rejects_invalid_export_layout_type() -> None:
    with pytest.raises(TypeError, match=r"ExecutionRequest\.export_layout"):
        _ = ExecutionRequest(export_layout="nope")  # type: ignore[arg-type] contract validation boundary


def test_execution_request_rejects_invalid_output_type() -> None:
    with pytest.raises(TypeError, match=r"ExecutionRequest\.output"):
        _ = ExecutionRequest(export_layout=ExportLayout(field_ids=()), output="nope")  # type: ignore[arg-type] contract validation boundary


def test_execution_request_rejects_invalid_sink_type() -> None:
    with pytest.raises(TypeError, match=r"ExecutionRequest\.sink"):
        _ = ExecutionRequest(
            export_layout=ExportLayout(field_ids=()),
            output=OutputSpec(path=None),
            sink=object(),  # type: ignore[arg-type] contract validation boundary
        )


def test_execution_request_rejects_invalid_batch_size_types_and_values() -> None:
    with pytest.raises(TypeError, match=r"ExecutionRequest\.batch_size"):
        _ = ExecutionRequest(export_layout=ExportLayout(field_ids=()), batch_size=True)  # type: ignore[arg-type] contract validation boundary

    with pytest.raises(ValueError, match=r"ExecutionRequest\.batch_size"):
        _ = ExecutionRequest(export_layout=ExportLayout(field_ids=()), batch_size=0)


def test_execution_request_rejects_invalid_max_workers_types_and_values() -> None:
    with pytest.raises(TypeError, match=r"ExecutionRequest\.max_workers"):
        _ = ExecutionRequest(export_layout=ExportLayout(field_ids=()), max_workers=True)  # type: ignore[arg-type] contract validation boundary

    with pytest.raises(ValueError, match=r"ExecutionRequest\.max_workers"):
        _ = ExecutionRequest(export_layout=ExportLayout(field_ids=()), max_workers=-1)


def test_execution_request_rejects_invalid_parallel_mode() -> None:
    with pytest.raises(ValueError, match=r"ExecutionRequest\.parallel_mode"):
        _ = ExecutionRequest(export_layout=ExportLayout(field_ids=()), parallel_mode="nope")  # type: ignore[arg-type] contract validation boundary


def test_execution_request_rejects_invalid_chunk_parallelism_options() -> None:
    with pytest.raises(TypeError, match=r"ExecutionRequest\.parallelize_lookup_chunks"):
        _ = ExecutionRequest(
            export_layout=ExportLayout(field_ids=()),
            parallelize_lookup_chunks="yes",  # type: ignore[arg-type] contract validation boundary
        )

    with pytest.raises(TypeError, match=r"ExecutionRequest\.max_chunk_workers"):
        _ = ExecutionRequest(export_layout=ExportLayout(field_ids=()), max_chunk_workers=True)  # type: ignore[arg-type] contract validation boundary

    with pytest.raises(ValueError, match=r"ExecutionRequest\.max_chunk_workers"):
        _ = ExecutionRequest(export_layout=ExportLayout(field_ids=()), max_chunk_workers=0)


def test_execution_request_accepts_chunk_parallelism_opt_in() -> None:
    req = ExecutionRequest(
        export_layout=ExportLayout(field_ids=("id",)),
        parallel_mode="adaptive",
        parallelize_lookup_chunks=True,
        max_chunk_workers=2,
    )
    assert req.parallelize_lookup_chunks is True
    assert req.max_chunk_workers == 2


def test_execution_request_rejects_invalid_capture_in_memory_rows_type() -> None:
    with pytest.raises(TypeError, match=r"ExecutionRequest\.capture_in_memory_rows"):
        _ = ExecutionRequest(
            export_layout=ExportLayout(field_ids=()),
            capture_in_memory_rows="nope",  # type: ignore[arg-type] contract validation boundary
        )


def test_execution_request_rejects_invalid_key_normalization_type() -> None:
    with pytest.raises(TypeError, match=r"ExecutionRequest\.key_normalization"):
        _ = ExecutionRequest(export_layout=ExportLayout(field_ids=()), key_normalization=1)  # type: ignore[arg-type] contract validation boundary


def test_execution_request_accepts_valid_sink_and_none_batch_size() -> None:
    sink = InMemoryRowDataSink()
    req = ExecutionRequest(
        export_layout=ExportLayout(field_ids=("id",)),
        sink=sink,
        batch_size=None,
    )
    assert req.sink is sink
    assert req.batch_size is None


def test_execution_request_warns_on_extreme_max_workers() -> None:
    with pytest.warns(UserWarning, match=r"extremely large"):
        _ = ExecutionRequest(export_layout=ExportLayout(field_ids=("id",)), max_workers=257)
