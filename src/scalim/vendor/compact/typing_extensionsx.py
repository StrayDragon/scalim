from __future__ import annotations

import sys
from typing import Literal, TypedDict

__all__ = ["Literal", "Self", "TypedDict", "override"]


# region override compat (stdlib: 3.12+)
if sys.version_info >= (3, 12):
    from typing import override  # pyright: ignore[reportUnusedImport]
else:  # pragma: no cover
    from typing_extensions import override  # pyright: ignore[reportUnusedImport]
# endregion


# region Self compat (stdlib: 3.11+)
if sys.version_info >= (3, 11):
    from typing import Self  # pyright: ignore[reportUnusedImport]
else:  # pragma: no cover
    from typing_extensions import Self  # pyright: ignore[reportUnusedImport]
# endregion
