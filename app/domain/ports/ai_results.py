from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    text: str
    category: str


class FastTrackResultData(BaseModel):
    pass_fail: bool
    score: int = Field(ge=0, le=100)
    explanation: str
    candidate_name: str | None = None


class DeepAnalysisData(BaseModel):
    overall_score: int = Field(ge=0, le=100)
    strengths: list[str]
    weaknesses: list[str]
    risks: list[str]
    detailed_reasoning: str
    evidence: list[EvidenceItem]
