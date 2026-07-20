from pydantic import BaseModel


class EvidenceItem(BaseModel):
    text: str
    category: str


class FastTrackResultData(BaseModel):
    pass_fail: bool
    score: int
    explanation: str
    candidate_name: str | None = None


class DeepAnalysisData(BaseModel):
    overall_score: int
    strengths: list[str]
    weaknesses: list[str]
    risks: list[str]
    detailed_reasoning: str
    evidence: list[EvidenceItem]
