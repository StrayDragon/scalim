"""原子临时路径辅助:创建/替换/尽力清理.

供 `sinks`、`workflow` 与 `openpyxl` 辅助共用,避免 `_internal.utils` 反向依赖 `sinks`.
运行时需兼容 `Python 3.6`.
"""

import os
import tempfile
from contextlib import suppress
from pathlib import Path

_PRIVATE_TEMP_DIR_PREFIX = ".scalim-tmp-"


def _is_private_temp_dir(path: Path) -> bool:
    return bool(path.name) and path.name.startswith(_PRIVATE_TEMP_DIR_PREFIX)


def _best_effort_cleanup_private_temp_dir(private_dir: Path) -> None:
    if not _is_private_temp_dir(private_dir):
        return
    with suppress(OSError):
        private_dir.rmdir()


def best_effort_cleanup_temp_path_dir(temp_path: str) -> None:
    temp_obj = Path(temp_path)
    _best_effort_cleanup_private_temp_dir(temp_obj.parent)


def best_effort_remove_temp_path(temp_path: str) -> None:
    temp_obj = Path(temp_path)
    with suppress(OSError):
        temp_obj.unlink()
    _best_effort_cleanup_private_temp_dir(temp_obj.parent)


def atomic_replace_temp_path(temp_path: str, output_path: str) -> None:
    temp_obj = Path(temp_path)
    _ = temp_obj.replace(output_path)
    _best_effort_cleanup_private_temp_dir(temp_obj.parent)


def create_temp_path(output_path: str, suffix: str) -> str:
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    private_dir = Path(tempfile.mkdtemp(dir=str(output_dir), prefix=_PRIVATE_TEMP_DIR_PREFIX))
    with suppress(OSError):
        private_dir.chmod(0o700)

    fd, temp_path = tempfile.mkstemp(suffix=suffix, dir=str(private_dir))
    os.close(fd)
    return str(temp_path)


__all__ = ()
