import logging
import os
import platform
from pathlib import Path
from typing import Any, Optional, Tuple

from ...._project_constants import VIZ_DIR_NAME
from ....vendor.dataclassesx import dataclass, field

_LOGGER = logging.getLogger(__name__)


def default_viz_dir() -> str:
    system = platform.system().lower()
    if system.startswith("win") or os.name == "nt":
        base = Path(os.environ.get("APPDATA") or r"~\AppData\Roaming").expanduser()
    elif system == "darwin":
        base = Path("~/Library/Application Support").expanduser()
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or "~/.config").expanduser()
    return str(base / VIZ_DIR_NAME)


def normalize_output_dir(base_dir: str) -> str:
    normalized = Path(base_dir).expanduser()
    base_name = normalized.name
    parent_name = normalized.parent.name
    if VIZ_DIR_NAME not in (base_name, parent_name):
        normalized = normalized / VIZ_DIR_NAME
    return str(normalized)


@dataclass
class VizObserverConfig:
    run_id: Optional[str] = None
    """可选:运行标识(用于推导 `output_dir/<run_id>` 与写入事件 `run_id` 字段).

    - 当未提供时, `VizObserver` 会在首次写入时生成一个时间戳 `run_id`.
    - 该字段主要用于工作流 `bundle` 等需要稳定运行目录名称的场景.
    """

    output_path: Optional[str] = None
    """事件输出文件路径(优先级高于 `output_dir`)."""

    output_dir: Optional[str] = None
    """输出目录;在未显式提供 `output_path`/`snapshot_path`/`trace_path` 时用于推导各输出文件路径."""

    snapshot_path: Optional[str] = None
    """快照输出文件路径(写入 `viz_snapshot.json`)."""

    trace_path: Optional[str] = None
    """追踪输出文件路径(写入 `viz_trace.jsonl`,需 `trace_enabled=True`)."""

    events_filename: str = "viz_events.jsonl"
    """当使用 `output_dir` 推导路径时的事件文件名."""

    trace_filename: str = "viz_trace.jsonl"
    """当使用 `output_dir` 推导路径时的追踪文件名."""

    snapshot_filename: str = "viz_snapshot.json"
    """当使用 `output_dir` 推导路径时的快照文件名."""

    use_default_output_dir: bool = False
    """是否在未提供 `output_dir` 时使用默认目录(不同系统下会落到不同的配置目录)."""

    trace_enabled: bool = False
    """是否启用追踪输出(除非显式启用,否则仅输出事件与快照)."""

    append: bool = False
    """是否以追加方式写入 `*.jsonl` 输出(避免覆盖既有结果)."""

    payload_policy: str = "summary"
    """事件负载策略:`summary`/`sample`/`full`/`none`."""

    sample_size: int = 5
    """当负载策略包含 `sample` 时,样本截断大小."""

    run_name: Optional[str] = None
    """可选的运行名称(写入 `snapshot.meta.viz.run_name`)."""

    env: Optional[str] = None
    """可选的环境标识(写入 `snapshot.meta.viz.env`)."""

    logger: logging.Logger = field(default=_LOGGER)
    """用于输出告警/异常日志的 `logging.Logger`."""

    def is_enabled(self) -> bool:
        events_path, snapshot_path, trace_path = self.resolve_output_paths()
        return bool(events_path or snapshot_path or (trace_path and self.trace_enabled_effective()))

    def trace_enabled_effective(self) -> bool:
        return bool(self.trace_enabled)

    def has_explicit_paths(self) -> bool:
        return bool(self.output_path or self.snapshot_path or self.trace_path)

    def _resolve_output_dir(self) -> Optional[str]:
        output_dir = self.output_dir
        if output_dir is None and self.use_default_output_dir:
            output_dir = default_viz_dir()
        if output_dir:
            return normalize_output_dir(output_dir)
        return None

    @staticmethod
    def _expand_user_path(path: Optional[str]) -> Optional[str]:
        if not path:
            return path
        return str(Path(path).expanduser())

    def _fill_paths_from_output_dir(
        self,
        output_dir: str,
        events_path: Optional[str],
        snapshot_path: Optional[str],
        trace_path: Optional[str],
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        base = Path(output_dir)
        if events_path is None:
            events_path = str(base / self.events_filename)
        if snapshot_path is None:
            snapshot_path = str(base / self.snapshot_filename)
        if trace_path is None:
            trace_path = str(base / self.trace_filename)
        return events_path, snapshot_path, trace_path

    def _infer_trace_path(
        self,
        trace_path: Optional[str],
        events_path: Optional[str],
        snapshot_path: Optional[str],
    ) -> Optional[str]:
        if trace_path is not None:
            return trace_path
        base_dir: Optional[Path] = None
        if events_path:
            base_dir = Path(events_path).parent
        elif snapshot_path:
            base_dir = Path(snapshot_path).parent
        if base_dir is None:
            return None
        return str(base_dir / self.trace_filename)

    def resolve_output_paths(self) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        output_dir = self._resolve_output_dir()
        events_path = self._expand_user_path(self.output_path)
        snapshot_path = self._expand_user_path(self.snapshot_path)
        trace_path = self._expand_user_path(self.trace_path)
        if output_dir:
            return self._fill_paths_from_output_dir(output_dir, events_path, snapshot_path, trace_path)
        trace_path = self._infer_trace_path(trace_path, events_path, snapshot_path)
        return events_path, snapshot_path, trace_path

    @classmethod
    def default_local(cls, **kwargs: Any) -> "VizObserverConfig":
        return cls(output_dir=default_viz_dir(), **kwargs)
