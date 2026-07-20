import uuid
from datetime import datetime, timezone

from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.fast_track_result import FastTrackResult
from app.domain.entities.job_description import JobDescription
from app.domain.entities.resume import Resume
from app.domain.value_objects import AnalysisStatus


class TestJobDescription:
    def test_create_with_minimal_fields(self) -> None:
        jd = JobDescription(
            title="Software Engineer",
            company="Acme Inc",
            original_content="We need a software engineer...",
            normalized_content="We need a software engineer...",
            file_path="/uploads/jds/uuid.pdf",
            file_type="pdf",
            injection_scan_passed=True,
        )
        assert jd.title == "Software Engineer"
        assert jd.company == "Acme Inc"
        assert isinstance(jd.id, uuid.UUID)
        assert jd.injection_scan_passed is True
        assert jd.injection_scan_details is None

    def test_create_with_all_fields(self) -> None:
        now = datetime.now(timezone.utc)
        jd_id = uuid.uuid4()
        jd = JobDescription(
            id=jd_id,
            title="Data Scientist",
            company="Corp",
            original_content="Looking for data scientist",
            normalized_content="Looking for data scientist",
            file_path="/uploads/jds/uuid2.pdf",
            file_type="pdf",
            injection_scan_passed=False,
            injection_scan_details={"issue": "suspicious"},
            created_at=now,
            updated_at=now,
        )
        assert jd.id == jd_id
        assert jd.created_at == now
        assert jd.injection_scan_details == {"issue": "suspicious"}


class TestResume:
    def test_create_with_minimal_fields(self) -> None:
        r = Resume(
            filename="resume.pdf",
            original_content="John Doe experience...",
            normalized_content="John Doe experience...",
            file_path="/uploads/resumes/uuid.pdf",
            file_type="pdf",
            injection_scan_passed=True,
        )
        assert r.filename == "resume.pdf"
        assert r.candidate_name is None
        assert r.email is None
        assert isinstance(r.id, uuid.UUID)

    def test_create_with_all_fields(self) -> None:
        r = Resume(
            filename="cv.docx",
            candidate_name="Jane Doe",
            email="jane@example.com",
            original_content="Jane is a Python developer",
            normalized_content="Jane is a Python developer",
            file_path="/uploads/resumes/uuid2.docx",
            file_type="docx",
            injection_scan_passed=True,
            injection_scan_details={"check": "clean"},
        )
        assert r.candidate_name == "Jane Doe"
        assert r.email == "jane@example.com"
        assert r.injection_scan_details == {"check": "clean"}


class TestFastTrackResult:
    def test_create(self) -> None:
        resume_id = uuid.uuid4()
        jd_id = uuid.uuid4()
        r = FastTrackResult(
            resume_id=resume_id,
            job_description_id=jd_id,
            pass_fail=True,
            score=85,
            explanation="Great fit",
            raw_response={"score": 85},
        )
        assert r.resume_id == resume_id
        assert r.job_description_id == jd_id
        assert r.pass_fail is True
        assert r.score == 85
        assert r.explanation == "Great fit"
        assert r.raw_response == {"score": 85}
        assert isinstance(r.id, uuid.UUID)

    def test_create_without_raw_response(self) -> None:
        r = FastTrackResult(
            resume_id=uuid.uuid4(),
            job_description_id=uuid.uuid4(),
            pass_fail=False,
            score=30,
            explanation="Poor match",
        )
        assert r.raw_response is None


class TestDeepAnalysis:
    def test_create_with_default_status(self) -> None:
        da = DeepAnalysis(
            resume_id=uuid.uuid4(),
            job_description_id=uuid.uuid4(),
        )
        assert da.status == AnalysisStatus.PENDING
        assert da.overall_score is None

    def test_create_with_full_data(self) -> None:
        da = DeepAnalysis(
            resume_id=uuid.uuid4(),
            job_description_id=uuid.uuid4(),
            status=AnalysisStatus.COMPLETED,
            overall_score=90,
            strengths=["Strong Python skills", "Leadership"],
            weaknesses=["No cloud experience"],
            risks=["Notice period too long"],
            detailed_reasoning="Overall a strong candidate",
            evidence=[{"skill": "Python", "proficiency": "expert"}],
            raw_response={"gemini_output": "..."},
        )
        assert da.status == AnalysisStatus.COMPLETED
        assert da.overall_score == 90
        assert da.strengths == ["Strong Python skills", "Leadership"]
        assert da.weaknesses == ["No cloud experience"]
        assert da.risks == ["Notice period too long"]
        assert da.detailed_reasoning == "Overall a strong candidate"
        assert da.evidence == [{"skill": "Python", "proficiency": "expert"}]

    def test_failed_analysis(self) -> None:
        da = DeepAnalysis(
            resume_id=uuid.uuid4(),
            job_description_id=uuid.uuid4(),
            status=AnalysisStatus.FAILED,
            error_message="Gemini API timeout",
        )
        assert da.status == AnalysisStatus.FAILED
        assert da.error_message == "Gemini API timeout"
        assert da.overall_score is None
