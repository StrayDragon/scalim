from typing import Mapping


def normalize_identity(result: Mapping[object, object], ctx: object) -> Mapping[object, object]:
    _ = ctx
    return result


def normalize_bad_return(result: Mapping[object, object], ctx: object) -> object:
    _ = (result, ctx)
    return []
