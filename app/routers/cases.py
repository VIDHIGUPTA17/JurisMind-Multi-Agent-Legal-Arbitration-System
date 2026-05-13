import uuid
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.case import Case, CaseType, CaseStatus
from app.models.user import User
from app.schemas.case import CaseCreateRequest, CaseResponse, CaseListResponse, JoinCaseRequest
from app.core.security import get_current_user_payload, hash_email

router = APIRouter(prefix="/cases", tags=["cases"])


@router.post("", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
async def create_case(
    body: CaseCreateRequest,
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    if payload.get("role") != "PARTY_A":
        raise HTTPException(status_code=403, detail="Only PARTY_A can create cases")

    try:
        case_type = CaseType(body.case_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid case_type: {body.case_type}")

    invite_token = secrets.token_urlsafe(32)
    party_b_email_hash = hash_email(str(body.party_b_email))

    case = Case(
        id=str(uuid.uuid4()),
        title=body.title,
        description=body.description,
        case_type=case_type,
        status=CaseStatus.OPEN,
        party_a_id=payload["sub"],
        party_b_invite_email_hash=party_b_email_hash,
        party_b_invite_token=invite_token,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(case)
    await db.flush()

    # In v1: print invite token to console (email integration deferred)
    print(f"\n[INVITE] Party B invite token for case {case.id}: {invite_token}\n")

    resp = CaseResponse(
        id=case.id,
        title=case.title,
        description=case.description,
        case_type=case.case_type.value,
        status=case.status.value,
        party_a_id=case.party_a_id,
        party_b_id=case.party_b_id,
        invite_token=invite_token,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )
    return resp


@router.post("/{case_id}/join", response_model=CaseResponse)
async def join_case(
    case_id: str,
    body: JoinCaseRequest,
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    if payload.get("role") != "PARTY_B":
        raise HTTPException(status_code=403, detail="Only PARTY_B can join a case")

    result = await db.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if case.party_b_id:
        raise HTTPException(status_code=400, detail="Case already has a respondent")
    if case.party_b_invite_token != body.invite_token:
        raise HTTPException(status_code=403, detail="Invalid invite token")

    case.party_b_id = payload["sub"]
    case.updated_at = datetime.now(timezone.utc)
    await db.flush()

    return CaseResponse(
        id=case.id, title=case.title, description=case.description,
        case_type=case.case_type.value, status=case.status.value,
        party_a_id=case.party_a_id, party_b_id=case.party_b_id,
        created_at=case.created_at, updated_at=case.updated_at,
    )


@router.get("", response_model=CaseListResponse)
async def list_cases(
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    user_id = payload["sub"]
    result = await db.execute(
        select(Case).where(
            (Case.party_a_id == user_id) | (Case.party_b_id == user_id)
        ).order_by(Case.created_at.desc())
    )
    cases = result.scalars().all()
    items = [
        CaseResponse(
            id=c.id, title=c.title, description=c.description,
            case_type=c.case_type.value, status=c.status.value,
            party_a_id=c.party_a_id, party_b_id=c.party_b_id,
            created_at=c.created_at, updated_at=c.updated_at,
        )
        for c in cases
    ]
    return CaseListResponse(cases=items, total=len(items))


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: str,
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    user_id = payload["sub"]
    if case.party_a_id != user_id and case.party_b_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return CaseResponse(
        id=case.id, title=case.title, description=case.description,
        case_type=case.case_type.value, status=case.status.value,
        party_a_id=case.party_a_id, party_b_id=case.party_b_id,
        created_at=case.created_at, updated_at=case.updated_at,
    )
