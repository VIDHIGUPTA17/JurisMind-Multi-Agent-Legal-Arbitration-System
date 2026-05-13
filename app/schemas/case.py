from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class CaseCreateRequest(BaseModel):
    title: str
    description: Optional[str] = None
    case_type: str  # CONTRACT | CONSUMER | PROPERTY | COMPANY
    party_b_email: EmailStr  # Invite email for Party B


class CaseResponse(BaseModel):
    id: str
    title: str
    description: Optional[str]
    case_type: str
    status: str
    party_a_id: str
    party_b_id: Optional[str]
    invite_token: Optional[str] = None  # Only shown to Party A on creation
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CaseListResponse(BaseModel):
    cases: list[CaseResponse]
    total: int


class JoinCaseRequest(BaseModel):
    invite_token: str
