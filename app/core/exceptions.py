import uuid


class AppError(Exception):
    """Base exception for the application."""


class UnsupportedFileTypeError(AppError):
    """Raised when an uploaded file type is not supported."""

    def __init__(self, file_type: str) -> None:
        self.file_type = file_type
        super().__init__(f"Unsupported file type: {file_type}")


class ParsingError(AppError):
    """Raised when document parsing fails."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(f"Parsing failed: {detail}")


class InjectionDetectedError(AppError):
    """Raised when prompt injection is detected in uploaded content."""

    def __init__(self, details: dict[str, object]) -> None:
        self.details = details
        super().__init__("Prompt injection detected in uploaded content")


class FileNotFoundError(AppError):
    """Raised when a requested file is not found."""

    def __init__(self, file_id: str) -> None:
        self.file_id = file_id
        super().__init__(f"File not found: {file_id}")


class AIResponseError(AppError):
    """Raised when the AI service returns an unexpected or malformed response."""

    def __init__(self, detail: str, raw_response: object = None) -> None:
        self.detail = detail
        self.raw_response = raw_response
        super().__init__(f"AI response error: {detail}")


class ResumeNotFoundError(AppError):
    """Raised when a resume ID cannot be found."""

    def __init__(self, resume_id: uuid.UUID) -> None:
        self.resume_id = resume_id
        super().__init__(f"Resume not found: {resume_id}")


class JobDescriptionNotFoundError(AppError):
    """Raised when a job description ID cannot be found."""

    def __init__(self, jd_id: uuid.UUID) -> None:
        self.jd_id = jd_id
        super().__init__(f"Job description not found: {jd_id}")


class AnalysisNotFoundError(AppError):
    """Raised when a deep analysis ID cannot be found."""

    def __init__(self, analysis_id: uuid.UUID) -> None:
        self.analysis_id = analysis_id
        super().__init__(f"Analysis not found: {analysis_id}")
