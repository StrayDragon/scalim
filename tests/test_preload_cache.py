import pickle

from scalim.execution.preload_cache import PreloadCache


def test_preload_cache_supports_basic_mapping_protocol_and_pickle_roundtrip() -> None:
    cache = PreloadCache()
    assert len(cache) == 0

    cache["a"] = {1: {"value": "x"}}
    assert len(cache) == 1
    assert cache["a"][1]["value"] == "x"
    assert list(iter(cache)) == ["a"]

    del cache["a"]
    assert len(cache) == 0

    calls = []

    def _load():  # type: ignore[no-untyped-def]
        calls.append(1)
        return {1: {"value": "y"}}

    first = cache.get_or_load("src", _load)
    second = cache.get_or_load("src", _load)
    assert first == {1: {"value": "y"}}
    assert second == {1: {"value": "y"}}
    assert len(calls) == 1

    data = pickle.dumps(cache)
    restored = pickle.loads(data)
    assert restored["src"] == {1: {"value": "y"}}

    restored.__setstate__({"_data": []})  # type: ignore[attr-defined]
    assert len(restored) == 0
