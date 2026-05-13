"""
Verdict router — v2 multi-agent orchestrator pipeline.

POST   /{case_id}/verdict                       → 202, starts background pipeline
GET    /{case_id}/verdict                       → full VerdictResponse
GET    /{case_id}/arbitration/stages            → all 7 stage statuses
GET    /{case_id}/arbitration/stages/{num}      → single stage detail
POST   /{case_id}/arbitration/resume            → resume from last FAILED stage
GET    /{case_id}/verdict/grounding             → grounding report JSON
GET    /{case_id}/verdict/bias                  → bias report JSON
"""
import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.case import Case, CaseStatus
from app.models.document import Document, DocumentProcessingStatus
from app.models.verdict import Verdict
from app.models.arbitration_stage import ArbitrationStage, StageStatus
from app.schemas.verdict import VerdictResponse
from app.schemas.arbitration import StagesListResponse, StageDetailResponse, StageResponse
from app.core.security import get_current_user_payload
from app.agents.orchestrator import ArbitrationOrchestrator
from app.database import AsyncSessionLocal as async_session_factory

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cases", tags=["verdicts"])


# ── helpers ──────────────────────────────────────────────────────────────────

async def _get_authorized_case(case_id: str, user_id: str, db: AsyncSession) -> Case:
    result = await db.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if case.party_a_id != user_id and case.party_b_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return case


async def _run_orchestrator(
    case_id: str,
    claimant_text: str,
    respondent_text: str,
) -> None:
    """Background task: runs the 7-stage pipeline and persists verdict."""
    async with async_session_factory() as session:
        try:
            result = await ArbitrationOrchestrator().run(
                case_id=case_id,
                claimant_docs=claimant_text,
                respondent_docs=respondent_text,
                session=session,
            )
            final_verdict = result["final_verdict"]
            grounding_report = result.get("grounding_report", {})
            bias_report = result.get("bias_report", {})
            settlement = result.get("settlement_recommendation", {})
            compensation = result.get("compensation_breakdown", {})

            # Persist verdict
            verdict = Verdict(
                id=str(uuid.uuid4()),
                case_id=case_id,
                agent_a_summary=json.dumps(result.get("claimant_summary", {})),
                agent_b_summary=json.dumps(result.get("respondent_summary", {})),
                judge_reasoning=final_verdict.get("reasoning", ""),
                verdict_text=final_verdict.get("verdict", ""),
                applicable_laws=final_verdict.get("applicable_laws", []),
                relief_awarded=json.dumps(final_verdict["relief_awarded"]) if isinstance(final_verdict.get("relief_awarded"), dict) else final_verdict.get("relief_awarded", ""),
                confidence_score=final_verdict.get("confidence_score"),
                grounding_report=grounding_report,
                bias_report=bias_report,
                settlement_recommendation=settlement,
                compensation_breakdown=compensation,
                stage_count=7,
                total_groq_tokens=result.get("total_groq_tokens", 0),
                total_duration_ms=result.get("total_duration_ms", 0),
                created_at=datetime.now(timezone.utc),
            )
            session.add(verdict)

            # Update case status
            case_result = await session.execute(select(Case).where(Case.id == case_id))
            case = case_result.scalar_one_or_none()
            if case:
                case.status = CaseStatus.VERDICT_DELIVERED
                case.updated_at = datetime.now(timezone.utc)

            await session.commit()
            logger.info("orchestrator_completed", extra={"case_id": case_id})

        except Exception as exc:
            logger.error("orchestrator_failed", extra={"case_id": case_id, "error": str(exc)})


# ── routes ────────────────────────────────────────────────────────────────────

@router.post("/{case_id}/verdict", status_code=status.HTTP_202_ACCEPTED)
async def trigger_verdict(
    case_id: str,
    background_tasks: BackgroundTasks,
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    """Enqueue the 7-stage AI arbitration pipeline. Returns 202 immediately."""
    user_id = payload["sub"]
    case = await _get_authorized_case(case_id, user_id, db)

    if case.status == CaseStatus.VERDICT_DELIVERED:
        raise HTTPException(status_code=400, detail="Verdict already delivered for this case")

    # Idempotency: reject if pipeline already running
    running = await db.execute(
        select(ArbitrationStage).where(
            ArbitrationStage.case_id == case_id,
            ArbitrationStage.status == StageStatus.RUNNING,
        )
    )
    if running.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Arbitration pipeline already running")

    allowed_statuses = (CaseStatus.PARTY_B_RESPONDED, CaseStatus.IN_ARBITRATION)
    if case.status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail="Both parties must file documents before triggering verdict",
        )

    # Verify all documents processed
    docs_result = await db.execute(select(Document).where(Document.case_id == case_id))
    all_docs = docs_result.scalars().all()
    unprocessed = [d for d in all_docs if d.processing_status != DocumentProcessingStatus.DONE]
    if unprocessed:
        raise HTTPException(
            status_code=400,
            detail=f"{len(unprocessed)} document(s) still processing. Please wait.",
        )

    party_a_docs = [d for d in all_docs if d.uploader_id == case.party_a_id]
    party_b_docs = [d for d in all_docs if d.uploader_id == case.party_b_id]
    if not party_a_docs:
        raise HTTPException(status_code=400, detail="Claimant has not filed any documents")
    if not party_b_docs:
        raise HTTPException(status_code=400, detail="Respondent has not filed any documents")

    claimant_text = "\n\n=== DOCUMENT BREAK ===\n\n".join(
        d.content_anonymized or "" for d in party_a_docs
    )
    respondent_text = "\n\n=== DOCUMENT BREAK ===\n\n".join(
        d.content_anonymized or "" for d in party_b_docs
    )

    case.status = CaseStatus.IN_ARBITRATION
    case.updated_at = datetime.now(timezone.utc)
    await db.commit()

    background_tasks.add_task(_run_orchestrator, case_id, claimant_text, respondent_text)
    logger.info("arbitration_enqueued", extra={"case_id": case_id, "user_id": user_id})

    return {"case_id": case_id, "status": "processing", "message": "Arbitration pipeline started"}


@router.get("/{case_id}/verdict", response_model=VerdictResponse)
async def get_verdict(
    case_id: str,
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    user_id = payload["sub"]
    await _get_authorized_case(case_id, user_id, db)

    v_result = await db.execute(select(Verdict).where(Verdict.case_id == case_id))
    verdict = v_result.scalar_one_or_none()
    if not verdict:
        raise HTTPException(status_code=404, detail="No verdict yet for this case")

    return VerdictResponse.model_validate(verdict)


@router.get("/{case_id}/arbitration/stages", response_model=StagesListResponse)
async def list_stages(
    case_id: str,
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    user_id = payload["sub"]
    await _get_authorized_case(case_id, user_id, db)

    result = await db.execute(
        select(ArbitrationStage)
        .where(ArbitrationStage.case_id == case_id)
        .order_by(ArbitrationStage.stage_number)
    )
    stages = result.scalars().all()

    completed = sum(1 for s in stages if s.status == StageStatus.COMPLETED)
    return StagesListResponse(
        case_id=case_id,
        current_stage=completed,
        total_stages=7,
        stages=[StageResponse.model_validate(s) for s in stages],
    )


@router.get("/{case_id}/arbitration/stages/{stage_number}", response_model=StageDetailResponse)
async def get_stage(
    case_id: str,
    stage_number: int,
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    user_id = payload["sub"]
    await _get_authorized_case(case_id, user_id, db)

    result = await db.execute(
        select(ArbitrationStage).where(
            ArbitrationStage.case_id == case_id,
            ArbitrationStage.stage_number == stage_number,
        )
    )
    stage = result.scalar_one_or_none()
    if not stage:
        raise HTTPException(status_code=404, detail=f"Stage {stage_number} not found")

    return StageDetailResponse.model_validate(stage)


@router.post("/{case_id}/arbitration/resume", status_code=status.HTTP_202_ACCEPTED)
async def resume_arbitration(
    case_id: str,
    background_tasks: BackgroundTasks,
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    """Resume pipeline from the last FAILED stage by re-running from scratch."""
    user_id = payload["sub"]
    case = await _get_authorized_case(case_id, user_id, db)

    failed = await db.execute(
        select(ArbitrationStage).where(
            ArbitrationStage.case_id == case_id,
            ArbitrationStage.status == StageStatus.FAILED,
        )
    )
    if not failed.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="No failed stage to resume")

    docs_result = await db.execute(select(Document).where(Document.case_id == case_id))
    all_docs = docs_result.scalars().all()
    party_a_docs = [d for d in all_docs if d.uploader_id == case.party_a_id]
    party_b_docs = [d for d in all_docs if d.uploader_id == case.party_b_id]

    claimant_text = "\n\n=== DOCUMENT BREAK ===\n\n".join(
        d.content_anonymized or "" for d in party_a_docs
    )
    respondent_text = "\n\n=== DOCUMENT BREAK ===\n\n".join(
        d.content_anonymized or "" for d in party_b_docs
    )

    background_tasks.add_task(_run_orchestrator, case_id, claimant_text, respondent_text)
    logger.info("arbitration_resumed", extra={"case_id": case_id})
    return {"case_id": case_id, "status": "resuming"}


@router.get("/{case_id}/verdict/grounding")
async def get_grounding_report(
    case_id: str,
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    user_id = payload["sub"]
    await _get_authorized_case(case_id, user_id, db)

    v_result = await db.execute(select(Verdict).where(Verdict.case_id == case_id))
    verdict = v_result.scalar_one_or_none()
    if not verdict:
        raise HTTPException(status_code=404, detail="No verdict yet")

    return verdict.grounding_report or {}


@router.get("/{case_id}/verdict/bias")
async def get_bias_report(
    case_id: str,
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    user_id = payload["sub"]
    await _get_authorized_case(case_id, user_id, db)

    v_result = await db.execute(select(Verdict).where(Verdict.case_id == case_id))
    verdict = v_result.scalar_one_or_none()
    if not verdict:
        raise HTTPException(status_code=404, detail="No verdict yet")

    return verdict.bias_report or {}
