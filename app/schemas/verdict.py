from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Any


class VerdictResponse(BaseModel):
    id: str
    case_id: str
    agent_a_summary: Optional[str] = None
    agent_b_summary: Optional[str] = None
    judge_reasoning: Optional[str] = None
    verdict_text: Optional[str] = None
    applicable_laws: list = []
    relief_awarded: Optional[str] = None
    created_at: datetime
    # v2 enhanced fields
    confidence_score: Optional[float] = None
    grounding_report: Optional[dict[str, Any]] = None
    bias_report: Optional[dict[str, Any]] = None
    settlement_recommendation: Optional[dict[str, Any]] = None
    compensation_breakdown: Optional[dict[str, Any]] = None

    model_config = {"from_attributes": True}
