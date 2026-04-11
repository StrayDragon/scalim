from pathlib import Path

from scalim.sinks._internal.base import atomic_replace_temp_path, best_effort_remove_temp_path, create_temp_path


def test_create_temp_path_resides_in_private_dir(tmp_path: Path) -> None:
    output_path = tmp_path / "out" / "report.csv"
    temp_path = create_temp_path(str(output_path), ".csv.tmp")
    temp_obj = Path(temp_path)

    assert temp_obj.exists()
    assert temp_obj.parent.name.startswith(".scalim-tmp-")
    assert temp_obj.parent.parent == output_path.parent


def test_create_temp_path_is_unique_per_call(tmp_path: Path) -> None:
    output_path = tmp_path / "out" / "report.csv"
    first = create_temp_path(str(output_path), ".csv.tmp")
    second = create_temp_path(str(output_path), ".csv.tmp")

    assert first != second


def test_atomic_replace_temp_path_cleans_private_dir(tmp_path: Path) -> None:
    output_path = tmp_path / "out" / "report.csv"
    temp_path = create_temp_path(str(output_path), ".csv.tmp")
    temp_obj = Path(temp_path)
    private_dir = temp_obj.parent

    temp_obj.write_text("hello", encoding="utf-8")
    atomic_replace_temp_path(temp_path, str(output_path))

    assert output_path.read_text(encoding="utf-8") == "hello"
    assert not private_dir.exists()


def test_atomic_replace_temp_path_does_not_raise_when_dir_not_empty(tmp_path: Path) -> None:
    output_path = tmp_path / "out" / "report.csv"
    temp_path = create_temp_path(str(output_path), ".csv.tmp")
    temp_obj = Path(temp_path)
    private_dir = temp_obj.parent

    extra = private_dir / "keep.txt"
    extra.write_text("x", encoding="utf-8")

    temp_obj.write_text("hello", encoding="utf-8")
    atomic_replace_temp_path(temp_path, str(output_path))

    assert private_dir.exists()

    best_effort_remove_temp_path(str(extra))
    assert not private_dir.exists()
