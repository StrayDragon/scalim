import secrets
import time
from typing import Any, Callable, Dict, Optional, Tuple, TypeVar

from ..events import EVENT_LOADER_RETRY
from ..vendor.dataclassesx import dataclass, field

CALLSITE_LOAD = "load"
CALLSITE_LOAD_REF = "load_ref"
CALLSITE_PRELOAD_FOREVER = "preload_forever"
CALLSITE_MAIN_SOURCE = "main_source"


DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_MAX_ELAPSED_SECONDS = 10.0
DEFAULT_BACKOFF = "exponential"
DEFAULT_BASE_DELAY_SECONDS = 0.2
DEFAULT_MAX_DELAY_SECONDS = 2.0
DEFAULT_JITTER = True

HARD_CAP_MAX_ATTEMPTS = 5
HARD_CAP_MAX_ELAPSED_SECONDS = 20.0
HARD_CAP_MAX_DELAY_SECONDS = 5.0

_T = TypeVar("_T")

_JITTER_BITS = 53
_JITTER_MAX = float(1 << _JITTER_BITS)


@dataclass(frozen=True)
class LoaderRetryContext:
    """传递给用户提供的 `should_retry(exc, ctx)` 回调的上下文."""

    loader_name: str
    callsite: str
    attempt_num: int
    max_attempts: int
    elapsed_seconds: float


ShouldRetryFn = Callable[[Exception, LoaderRetryContext], bool]


@dataclass(frozen=True)
class LoaderRetryPolicySpec:
    """重试策略的局部覆盖层.

    所有字段均可选;合并到基础策略时,非 `None` 的值会覆盖基础值.
    """

    enabled: Optional[bool] = None
    should_retry: Optional[ShouldRetryFn] = None
    max_attempts: Optional[int] = None
    max_elapsed_seconds: Optional[float] = None
    backoff: Optional[str] = None
    base_delay_seconds: Optional[float] = None
    max_delay_seconds: Optional[float] = None
    jitter: Optional[bool] = None


@dataclass(frozen=True)
class LoaderRetryPolicy:
    """单次加载调用的生效重试策略."""

    enabled: bool = False
    should_retry: Optional[ShouldRetryFn] = None
    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    max_elapsed_seconds: float = DEFAULT_MAX_ELAPSED_SECONDS
    backoff: str = DEFAULT_BACKOFF
    base_delay_seconds: float = DEFAULT_BASE_DELAY_SECONDS
    max_delay_seconds: float = DEFAULT_MAX_DELAY_SECONDS
    jitter: bool = DEFAULT_JITTER

    def __post_init__(self) -> None:
        _validate_enabled_and_should_retry(enabled=self.enabled, should_retry=self.should_retry)
        _validate_max_attempts(max_attempts=self.max_attempts)
        _validate_max_elapsed_seconds(max_elapsed_seconds=self.max_elapsed_seconds)
        _validate_backoff(backoff=self.backoff)
        _validate_base_delay_seconds(base_delay_seconds=self.base_delay_seconds)
        _validate_max_delay_seconds(max_delay_seconds=self.max_delay_seconds)
        _validate_jitter(jitter=self.jitter)

    @classmethod
    def disabled(cls) -> "LoaderRetryPolicy":
        return cls(enabled=False)

    def next_sleep_seconds(self, *, attempt_num: int) -> float:
        backoff = str(self.backoff or "").strip().lower()
        if backoff == "fixed":
            delay = self.base_delay_seconds
        else:
            # `attempt_num` 从 1 开始;第 1 次失败使用基准延迟乘 `2**0`.
            delay = self.base_delay_seconds * (2 ** max(0, int(attempt_num) - 1))

        delay = min(delay, self.max_delay_seconds)
        if delay <= 0:
            return 0.0

        if not self.jitter:
            return float(delay)
        jitter = _secure_unit_random() * float(delay)
        return float(min(self.max_delay_seconds, max(0.0, float(jitter))))


@dataclass(frozen=True)
class LoaderRetryPolicies:
    """一次运行的生效重试策略: 默认策略 + 按加载器覆盖."""

    default: LoaderRetryPolicy = field(default_factory=LoaderRetryPolicy.disabled)
    by_loader: Dict[str, LoaderRetryPolicy] = field(default_factory=dict)

    @classmethod
    def disabled(cls) -> "LoaderRetryPolicies":
        return cls(default=LoaderRetryPolicy.disabled(), by_loader={})

    def resolve(self, loader_name: str) -> LoaderRetryPolicy:
        return self.by_loader.get(loader_name, self.default)


@dataclass(frozen=True)
class LoaderRetryPoliciesSpec:
    """驱动侧提供的重试策略覆盖项(局部).

    用于 `DSL` 适配器(例如 `YAML` 运行时)与配置派生的策略合并.
    """

    default: Optional[LoaderRetryPolicySpec] = None
    by_loader: Dict[str, LoaderRetryPolicySpec] = field(default_factory=dict)


def merge_loader_retry_policy(base: LoaderRetryPolicy, spec: Optional[LoaderRetryPolicySpec]) -> LoaderRetryPolicy:
    if spec is None:
        return base
    return LoaderRetryPolicy(
        enabled=spec.enabled if spec.enabled is not None else base.enabled,
        should_retry=spec.should_retry if spec.should_retry is not None else base.should_retry,
        max_attempts=spec.max_attempts if spec.max_attempts is not None else base.max_attempts,
        max_elapsed_seconds=spec.max_elapsed_seconds if spec.max_elapsed_seconds is not None else base.max_elapsed_seconds,
        backoff=spec.backoff if spec.backoff is not None else base.backoff,
        base_delay_seconds=spec.base_delay_seconds if spec.base_delay_seconds is not None else base.base_delay_seconds,
        max_delay_seconds=spec.max_delay_seconds if spec.max_delay_seconds is not None else base.max_delay_seconds,
        jitter=spec.jitter if spec.jitter is not None else base.jitter,
    )


def _safe_should_retry(should_retry: ShouldRetryFn, exc: Exception, ctx: LoaderRetryContext) -> bool:
    try:
        return bool(should_retry(exc, ctx))
    except Exception:  # noqa: BLE001
        return False


def _truncate_message(message: str, *, max_len: int) -> str:
    if not message:
        return ""
    msg = str(message)
    if len(msg) <= max_len:
        return msg
    return msg[: max(0, int(max_len) - 3)] + "..."


def _secure_unit_random() -> float:
    # 生成 53 位随机小数,用于 `IEEE-754` 双精度尾数.
    return float(secrets.randbits(_JITTER_BITS)) / _JITTER_MAX


def _validate_enabled_and_should_retry(*, enabled: Any, should_retry: Optional[Any]) -> None:
    if not isinstance(enabled, bool):
        msg = "LoaderRetryPolicy.enabled must be a bool"
        raise TypeError(msg)
    if enabled and should_retry is None:
        msg = "LoaderRetryPolicy.enabled=true requires should_retry"
        raise ValueError(msg)
    if should_retry is not None and not callable(should_retry):
        msg = "LoaderRetryPolicy.should_retry must be callable"
        raise TypeError(msg)


def _validate_max_attempts(*, max_attempts: Any) -> None:
    if not isinstance(max_attempts, int) or isinstance(max_attempts, bool):
        msg = "LoaderRetryPolicy.max_attempts must be an int"
        raise TypeError(msg)
    if max_attempts < 1:
        msg = "LoaderRetryPolicy.max_attempts must be >= 1"
        raise ValueError(msg)
    if max_attempts > HARD_CAP_MAX_ATTEMPTS:
        msg = "LoaderRetryPolicy.max_attempts must be <= {}".format(HARD_CAP_MAX_ATTEMPTS)
        raise ValueError(msg)


def _validate_max_elapsed_seconds(*, max_elapsed_seconds: Any) -> None:
    if not isinstance(max_elapsed_seconds, (int, float)) or isinstance(max_elapsed_seconds, bool):
        msg = "LoaderRetryPolicy.max_elapsed_seconds must be a number"
        raise TypeError(msg)
    if float(max_elapsed_seconds) <= 0:
        msg = "LoaderRetryPolicy.max_elapsed_seconds must be > 0"
        raise ValueError(msg)
    if float(max_elapsed_seconds) > HARD_CAP_MAX_ELAPSED_SECONDS:
        msg = "LoaderRetryPolicy.max_elapsed_seconds must be <= {}".format(HARD_CAP_MAX_ELAPSED_SECONDS)
        raise ValueError(msg)


def _validate_backoff(*, backoff: Any) -> None:
    if not isinstance(backoff, str):
        msg = "LoaderRetryPolicy.backoff must be a string"
        raise TypeError(msg)
    normalized = str(backoff or "").strip().lower()
    if normalized not in ("fixed", "exponential"):
        msg = "LoaderRetryPolicy.backoff must be 'fixed' or 'exponential'"
        raise ValueError(msg)


def _validate_base_delay_seconds(*, base_delay_seconds: Any) -> None:
    if not isinstance(base_delay_seconds, (int, float)) or isinstance(base_delay_seconds, bool):
        msg = "LoaderRetryPolicy.base_delay_seconds must be a number"
        raise TypeError(msg)
    if float(base_delay_seconds) < 0:
        msg = "LoaderRetryPolicy.base_delay_seconds must be >= 0"
        raise ValueError(msg)


def _validate_max_delay_seconds(*, max_delay_seconds: Any) -> None:
    if not isinstance(max_delay_seconds, (int, float)) or isinstance(max_delay_seconds, bool):
        msg = "LoaderRetryPolicy.max_delay_seconds must be a number"
        raise TypeError(msg)
    if float(max_delay_seconds) < 0:
        msg = "LoaderRetryPolicy.max_delay_seconds must be >= 0"
        raise ValueError(msg)
    if float(max_delay_seconds) > HARD_CAP_MAX_DELAY_SECONDS:
        msg = "LoaderRetryPolicy.max_delay_seconds must be <= {}".format(HARD_CAP_MAX_DELAY_SECONDS)
        raise ValueError(msg)


def _validate_jitter(*, jitter: Any) -> None:
    if not isinstance(jitter, bool):
        msg = "LoaderRetryPolicy.jitter must be a bool"
        raise TypeError(msg)


def _build_error_context(
    *,
    loader_name: str,
    callsite: str,
    batch_num: Optional[int],
    attempt_num: int,
    max_attempts: int,
    elapsed_seconds: float,
    retry_reason: str,
) -> Dict[str, Any]:
    return {
        "loader_name": loader_name,
        "callsite": callsite,
        "batch_num": batch_num,
        "attempt_num": attempt_num,
        "max_attempts": max_attempts,
        "elapsed_seconds": float(elapsed_seconds),
        "retry_reason": str(retry_reason),
    }


def _emit_error(instrumentation: Any, exc: Exception, context: Dict[str, Any]) -> None:
    if instrumentation is None:
        return
    instrumentation.emit_error(exc, context)


def _retry_reason_and_sleep(
    *,
    policy: LoaderRetryPolicy,
    exc: Exception,
    ctx: LoaderRetryContext,
    elapsed_seconds: float,
) -> Tuple[Optional[str], float]:
    if ctx.attempt_num >= policy.max_attempts:
        return "max_attempts_exceeded", 0.0
    if elapsed_seconds >= policy.max_elapsed_seconds:
        return "max_elapsed_exceeded", 0.0

    should_retry = policy.should_retry
    if should_retry is None or not _safe_should_retry(should_retry, exc, ctx):
        return "should_retry_false", 0.0

    sleep_seconds = float(policy.next_sleep_seconds(attempt_num=ctx.attempt_num))
    if elapsed_seconds + sleep_seconds > policy.max_elapsed_seconds:
        return "max_elapsed_exceeded", sleep_seconds

    return None, sleep_seconds


def _emit_loader_retry_event(
    *,
    instrumentation: Any,
    loader_name: str,
    callsite: str,
    attempt_num: int,
    max_attempts: int,
    elapsed_seconds: float,
    sleep_seconds: float,
    exc: Exception,
    batch_num: Optional[int],
) -> None:
    if instrumentation is None:
        return
    if not instrumentation.wants(EVENT_LOADER_RETRY):
        return

    instrumentation.emit_loader_retry(
        loader_name=loader_name,
        callsite=callsite,
        attempt_num=int(attempt_num),
        max_attempts=int(max_attempts),
        elapsed_seconds=float(elapsed_seconds),
        sleep_seconds=float(sleep_seconds),
        error_type=type(exc).__name__,
        error_message=_truncate_message(str(exc), max_len=200) or None,
        batch_num=batch_num,
    )


def call_with_loader_retry(
    *,
    call: Callable[[], _T],
    instrumentation: Any,
    policy: LoaderRetryPolicy,
    loader_name: str,
    callsite: str,
    batch_num: Optional[int] = None,
) -> _T:
    """按重试策略调用加载函数.

    注意:
    - 仅捕获 `Exception`(不会捕获 `BaseException`).
    - 每次重试都会发出 `loader_retry` 事件.
    - 放弃重试时仅发出一次 `error` 事件,然后重新抛出原始异常.
    """
    if not policy.enabled:
        return call()

    start = time.monotonic()
    attempt_num = 0

    while True:
        attempt_num += 1
        try:
            return call()
        except Exception as exc:
            elapsed = time.monotonic() - start

            ctx = LoaderRetryContext(
                loader_name=loader_name,
                callsite=callsite,
                attempt_num=attempt_num,
                max_attempts=policy.max_attempts,
                elapsed_seconds=float(elapsed),
            )

            retry_reason, sleep_seconds = _retry_reason_and_sleep(
                policy=policy,
                exc=exc,
                ctx=ctx,
                elapsed_seconds=float(elapsed),
            )
            if retry_reason is not None:
                _emit_error(
                    instrumentation,
                    exc,
                    _build_error_context(
                        loader_name=loader_name,
                        callsite=callsite,
                        batch_num=batch_num,
                        attempt_num=attempt_num,
                        max_attempts=policy.max_attempts,
                        elapsed_seconds=float(elapsed),
                        retry_reason=str(retry_reason),
                    ),
                )
                raise

            _emit_loader_retry_event(
                instrumentation=instrumentation,
                loader_name=loader_name,
                callsite=callsite,
                attempt_num=attempt_num,
                max_attempts=policy.max_attempts,
                elapsed_seconds=float(elapsed),
                sleep_seconds=float(sleep_seconds),
                exc=exc,
                batch_num=batch_num,
            )

            if sleep_seconds > 0:
                time.sleep(sleep_seconds)


__all__ = []
