import concurrent.futures

from scalim.events import generate_run_id


def test_generate_run_id_parallel_runs_get_distinct_ids() -> None:
    def _one(_: int) -> str:
        return generate_run_id()

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        ids = list(pool.map(_one, range(200)))

    assert len(ids) == 200
    assert len(set(ids)) == 200
    assert all(str(x).startswith("run_") for x in ids)
