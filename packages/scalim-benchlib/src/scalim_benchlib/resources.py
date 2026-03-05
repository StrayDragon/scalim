import statistics
import threading
from typing import Callable, Dict, Optional

try:
    import psutil  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - optional dependency
    psutil = None


class _BenchmarkFixture:
    extra_info: Dict[str, object]

    def __call__(self, func: Callable[..., object], *args: object, **kwargs: object) -> object:
        raise NotImplementedError


class ResourceSampler:
    def __init__(self, interval: float = 0.05) -> None:
        self._interval = interval
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._rss_samples: list = []
        self._cpu_samples: list = []
        self._proc = None

    def start(self) -> None:
        if psutil is None:
            return
        self._proc = psutil.Process()
        self._proc.cpu_percent(interval=None)
        self._thread = threading.Thread(target=self._run, name="scalim-benchlib-resource-sampler")
        self._thread.daemon = True
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            if self._proc is not None:
                try:
                    self._rss_samples.append(self._proc.memory_info().rss)
                    self._cpu_samples.append(self._proc.cpu_percent(interval=None))
                except (OSError, RuntimeError):
                    continue
            self._stop.wait(self._interval)

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)

    def summary(self) -> Dict[str, Optional[float]]:
        rss_peak = max(self._rss_samples) if self._rss_samples else None
        rss_avg = statistics.mean(self._rss_samples) if self._rss_samples else None
        cpu_avg = statistics.mean(self._cpu_samples) if self._cpu_samples else None
        return {
            "rss_peak_mb": _bytes_to_mb(rss_peak) if rss_peak is not None else None,
            "rss_avg_mb": _bytes_to_mb(rss_avg) if rss_avg is not None else None,
            "cpu_avg_pct": cpu_avg,
        }


class BenchmarkRunner:
    def __init__(self, benchmark: _BenchmarkFixture, interval: float = 0.05) -> None:
        self._benchmark = benchmark
        self._interval = interval

    def run(self, func: Callable[..., object], *args: object, extra_info: Optional[Dict[str, object]] = None, **kwargs: object) -> object:
        sampler = ResourceSampler(interval=self._interval)
        sampler.start()
        try:
            result = self._benchmark(func, *args, **kwargs)
        finally:
            sampler.stop()
        info = sampler.summary()
        if extra_info is not None:
            info.update(extra_info)
        self._benchmark.extra_info.update(info)
        return result


def run_benchmark(benchmark: _BenchmarkFixture, func: Callable[..., object], *args: object, **kwargs: object) -> object:
    """Run benchmark with resource sampling."""
    runner = BenchmarkRunner(benchmark)
    return runner.run(func, *args, **kwargs)


def _bytes_to_mb(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return value / (1024.0 * 1024.0)
