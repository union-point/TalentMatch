import pytest

from app.domain.value_objects import AnalysisStatus, InjectionScanResult, Score


class TestScore:
    def test_valid_score(self) -> None:
        s = Score(75)
        assert s.value == 75

    def test_score_zero(self) -> None:
        s = Score(0)
        assert s.value == 0

    def test_score_hundred(self) -> None:
        s = Score(100)
        assert s.value == 100

    def test_score_below_zero(self) -> None:
        with pytest.raises(ValueError, match="Score must be between 0 and 100"):
            Score(-1)

    def test_score_above_hundred(self) -> None:
        with pytest.raises(ValueError, match="Score must be between 0 and 100"):
            Score(101)

    def test_score_equality(self) -> None:
        assert Score(50) == Score(50)
        assert Score(50) != Score(51)
        assert Score(50) != 50

    def test_score_repr(self) -> None:
        assert repr(Score(42)) == "Score(42)"


class TestAnalysisStatus:
    def test_values(self) -> None:
        assert AnalysisStatus.PENDING.value == "pending"
        assert AnalysisStatus.IN_PROGRESS.value == "in_progress"
        assert AnalysisStatus.COMPLETED.value == "completed"
        assert AnalysisStatus.FAILED.value == "failed"

    def test_from_string(self) -> None:
        assert AnalysisStatus("pending") == AnalysisStatus.PENDING
        assert AnalysisStatus("completed") == AnalysisStatus.COMPLETED

    def test_invalid_value(self) -> None:
        with pytest.raises(ValueError):
            AnalysisStatus("unknown")


class TestInjectionScanResult:
    def test_passed_without_details(self) -> None:
        r = InjectionScanResult(passed=True)
        assert r.passed is True
        assert r.suspicion_score == 0
        assert r.details is None

    def test_failed_with_details(self) -> None:
        r = InjectionScanResult(
            passed=False, suspicion_score=75, details={"reason": "suspicious text"}
        )
        assert r.passed is False
        assert r.suspicion_score == 75
        assert r.details == {"reason": "suspicious text"}

    def test_immutability(self) -> None:
        r = InjectionScanResult(passed=True)
        with pytest.raises(AttributeError):
            r.passed = False  # type: ignore[misc]
