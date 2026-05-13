"""
Schemas for arbitration stage tracking and SSE events.
"""
from __future__ import annotations
from datetime import datetime
from typing import Any
from pydantic import BaseModel


class StageResponse(BaseModel):
    stage_number: int
    stage_name: str
    status: str
    agent_name: str | None
    input_summary: str | None
    output_summary: str | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: int | None
    groq_tokens_used: int | None

    model_config = {"from_attributes": True}


class StagesListResponse(BaseModel):
    case_id: str
    current_stage: int
    total_stages: int
    stages: list[StageResponse]


class StageDetailResponse(StageResponse):
    output_json: dict[str, Any] | None
    citations: list[dict] | None
