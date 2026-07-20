from dataclasses import dataclass
from enum import Enum


class AnalysisStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class Score:
    def __init__(self, value: int) -> None:
        if not 0 <= value <= 100:
            raise ValueError(f"Score must be between 0 and 100, got {value}")
        self._value = value

    @property
    def value(self) -> int:
        return self._value

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Score):
            return self._value == other._value
        return NotImplemented

    def __repr__(self) -> str:
        return f"Score({self._value})"


@dataclass(frozen=True)
class InjectionScanResult:
    passed: bool
    suspicion_score: int = 0
    details: dict[str, object] | None = None
