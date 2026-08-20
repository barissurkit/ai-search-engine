from collections.abc import Callable
from dataclasses import dataclass, field
from time import perf_counter

Clock = Callable[[], float]


@dataclass
class PipelineTimings:
    """Request-local, monotonic timing collector for the RAG answer lifecycle."""

    clock: Clock = perf_counter
    _started_at: float = field(init=False)
    _stages: dict[str, float] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self._started_at = self.clock()

    def start_stage(self) -> float:
        return self.clock()

    def record(self, name: str, started_at: float) -> None:
        self._stages[name] = max(0.0, (self.clock() - started_at) * 1000)

    def record_from_start(self, name: str) -> None:
        self.record(name, self._started_at)

    def has_stage(self, name: str) -> bool:
        return name in self._stages

    def finish(self) -> dict[str, float]:
        self.record_from_start("total_ms")
        return dict(self._stages)
