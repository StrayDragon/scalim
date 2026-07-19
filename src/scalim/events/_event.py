# region imports

import time
import uuid

# endregion


def now_ts() -> float:
    return time.time()


def generate_run_id(prefix: str = "run") -> str:
    return "{}_{}".format(prefix, uuid.uuid4().hex)


__all__ = ()
