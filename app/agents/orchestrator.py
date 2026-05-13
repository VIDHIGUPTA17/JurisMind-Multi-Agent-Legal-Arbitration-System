"""
Arbitration Orchestrator — controls the 7-stage multi-agent pipeline.
Stores each stage result to DB, broadcasts SSE events, handles retry.
"""
from __future__ import annotations
import asyncio
import json
import logging
import time
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.arbitration_stage import ArbitrationStage, StageStatus
from app.agents.party_agent import PartyAgent
from app.agents.evidence_comparison_agent import EvidenceComparisonAgent
from app.agents.contradiction_detection_agent import ContradictionDetectionAgent
from app.agents.witness_consistency_agent import WitnessConsistencyAgent
from app.agents.legal_argument_agent import LegalArgumentAgent
from app.agents.liability_reasoning_agent import LiabilityReasoningAgent
from app.agents.compensation_calculation_agent import CompensationCalculationAgent
from app.agents.settlement_recommendation_agent import SettlementRecommendationAgent
from app.agents.bias_conflict_agent import BiasConflictAgent
from app.agents.chief_judge_agent import ChiefJudgeAgent
from app.rag.retriever import retrieve_relevant_chunks
from app.rag.citation_tracker import CitationTracker

logger = logging.getLogger(__name__)

# Global SSE event queues: case_id → list of asyncio.Queue
_sse_queues: dict[str, list[asyncio.Queue]] = {}


def subscribe_to_case(case_id: str) -> asyncio.Queue:
    """Create a new SSE subscriber queue for a case."""
    q: asyncio.Queue = asyncio.Queue()
    _sse_queues.setdefault(case_id, []).append(q)
    return q


def unsubscribe_from_case(case_id: str, q: asyncio.Queue) -> None:
    queues = _sse_queues.get(case_id, [])
    if q in queues:
        queues.remove(q)


async def _broadcast(case_id: str, event_type: str, data: dict) -> None:
    """Broadcast an SSE event to all subscribers of a case."""
    queues = _sse_queues.get(case_id, [])
    for q in list(queues):
        try:
            await q.put({"type": event_type, "data": data})
        except Exception:
            pass


class ArbitrationOrchestrator:
    """
    Controls the 7-stage multi-agent pipeline.

    Stages:
    1. party_analysis         — PartyAgent × 2
    2. evidence_comparison    — EvidenceComparisonAgent
    3. contradiction_check    — ContradictionDetectionAgent + WitnessConsistencyAgent
    4. legal_reasoning        — LegalArgumentAgent + LiabilityReasoningAgent
    5. resolution             — CompensationCalculationAgent + SettlementRecommendationAgent
    6. quality_assurance      — BiasConflictAgent
    7. final_verdict          — ChiefJudgeAgent
    """

    async def run(
        self,
        case_id: str,
        claimant_docs: str,
        respondent_docs: str,
        session: AsyncSession,
    ) -> dict:
        context: dict = {
            "case_id": case_id,
            "claimant_docs": claimant_docs,
            "respondent_docs": respondent_docs,
        }
        total_tokens = 0
        t_start = time.time()

        # ── STAGE 1: Party Analysis ──────────────────────────────────────
        stage1 = await self._start_stage(case_id, 1, "party_analysis", "PartyAgent", session)
        try:
            loop = asyncio.get_running_loop()
            claimant_summary, respondent_summary = await asyncio.gather(
                loop.run_in_executor(None, lambda: PartyAgent().summarise("CLAIMANT", claimant_docs)),
                loop.run_in_executor(None, lambda: PartyAgent().summarise("RESPONDENT", respondent_docs)),
            )
            context["claimant_summary"] = claimant_summary
            context["respondent_summary"] = respondent_summary
            total_tokens += claimant_summary.pop("_tokens_used", 0) + respondent_summary.pop("_tokens_used", 0)
            summary_text = (
                f"Claimant: {len(claimant_summary.get('claims', []))} claims, "
                f"strength={claimant_summary.get('overall_strength_assessment', '?')}. "
                f"Respondent: {len(respondent_summary.get('defences', []))} defences, "
                f"strength={respondent_summary.get('overall_strength_assessment', '?')}."
            )
            await self._complete_stage(stage1, context, summary_text, session)
        except Exception as e:
            await self._fail_stage(stage1, str(e), session)
            raise

        # ── STAGE 2: Evidence Comparison ─────────────────────────────────
        stage2 = await self._start_stage(case_id, 2, "evidence_comparison", "EvidenceComparisonAgent", session)
        try:
            evidence_chunks = await retrieve_relevant_chunks(
                query="breach of contract payment obligation delivery",
                case_id=case_id,
                session=session,
                top_k=15,
            )
            loop = asyncio.get_running_loop()
            evidence_map = await loop.run_in_executor(
                None,
                lambda: EvidenceComparisonAgent().compare(
                    claimant_summary=context["claimant_summary"],
                    respondent_summary=context["respondent_summary"],
                    evidence_chunks=evidence_chunks,
                ),
            )
            context["evidence_map"] = evidence_map
            context["evidence_chunks"] = evidence_chunks
            total_tokens += evidence_map.pop("_tokens_used", 0)
            summary_text = (
                f"Analyzed {evidence_map.get('total_claims_analyzed', 0)} claims. "
                f"Supported: {evidence_map.get('supported_count', 0)}, "
                f"Not found: {evidence_map.get('not_found_count', 0)}, "
                f"Contradicted: {evidence_map.get('contradicted_count', 0)}."
            )
            await self._complete_stage(stage2, context, summary_text, session)
        except Exception as e:
            await self._fail_stage(stage2, str(e), session)
            raise

        # ── STAGE 3: Contradiction & Consistency ─────────────────────────
        stage3 = await self._start_stage(case_id, 3, "contradiction_check", "ContradictionDetectionAgent+WitnessConsistencyAgent", session)
        try:
            loop = asyncio.get_running_loop()
            contradiction_report, claimant_consistency, respondent_consistency = await asyncio.gather(
                loop.run_in_executor(None, lambda: ContradictionDetectionAgent().detect(
                    context["claimant_summary"], context["respondent_summary"], context["evidence_map"]
                )),
                loop.run_in_executor(None, lambda: WitnessConsistencyAgent().check_consistency("CLAIMANT", claimant_docs)),
                loop.run_in_executor(None, lambda: WitnessConsistencyAgent().check_consistency("RESPONDENT", respondent_docs)),
            )
            context["contradiction_report"] = contradiction_report
            context["claimant_consistency"] = claimant_consistency
            context["respondent_consistency"] = respondent_consistency
            total_tokens += (
                contradiction_report.pop("_tokens_used", 0)
                + claimant_consistency.pop("_tokens_used", 0)
                + respondent_consistency.pop("_tokens_used", 0)
            )
            summary_text = (
                f"Found {contradiction_report.get('contradiction_count', 0)} contradictions, "
                f"{contradiction_report.get('agreed_fact_count', 0)} agreed facts. "
                f"Claimant consistency: {claimant_consistency.get('consistency_score', '?')}, "
                f"Respondent consistency: {respondent_consistency.get('consistency_score', '?')}."
            )
            await self._complete_stage(stage3, context, summary_text, session)
        except Exception as e:
            await self._fail_stage(stage3, str(e), session)
            raise

        # ── STAGE 4: Legal Reasoning ─────────────────────────────────────
        stage4 = await self._start_stage(case_id, 4, "legal_reasoning", "LegalArgumentAgent+LiabilityReasoningAgent", session)
        try:
            loop = asyncio.get_running_loop()
            legal_analysis = await loop.run_in_executor(None, lambda: LegalArgumentAgent().generate_arguments(
                context["contradiction_report"],
                context["evidence_map"],
                context["claimant_summary"],
                context["respondent_summary"],
            ))
            context["legal_analysis"] = legal_analysis
            total_tokens += legal_analysis.pop("_tokens_used", 0)

            liability_determination = await loop.run_in_executor(None, lambda: LiabilityReasoningAgent().determine_liability(
                context["legal_analysis"],
                context["contradiction_report"],
            ))
            context["liability_determination"] = liability_determination
            total_tokens += liability_determination.pop("_tokens_used", 0)

            summary_text = (
                f"Identified {len(legal_analysis.get('legal_issues', []))} legal issues. "
                f"Primary liability: {liability_determination.get('primary_liability', '?')} "
                f"({liability_determination.get('liability_split', {})})."
            )
            await self._complete_stage(stage4, context, summary_text, session)
        except Exception as e:
            await self._fail_stage(stage4, str(e), session)
            raise

        # ── STAGE 5: Resolution ──────────────────────────────────────────
        stage5 = await self._start_stage(case_id, 5, "resolution", "CompensationCalculationAgent+SettlementRecommendationAgent", session)
        try:
            loop = asyncio.get_running_loop()
            compensation_breakdown, settlement_recommendation = await asyncio.gather(
                loop.run_in_executor(None, lambda: CompensationCalculationAgent().calculate(
                    context["liability_determination"],
                    context.get("evidence_chunks", []),
                    context["claimant_summary"],
                )),
                loop.run_in_executor(None, lambda: SettlementRecommendationAgent().recommend(
                    context["liability_determination"],
                    {},  # compensation not yet calculated; use liability
                )),
            )
            context["compensation_breakdown"] = compensation_breakdown
            context["settlement_recommendation"] = settlement_recommendation
            total_tokens += (
                compensation_breakdown.pop("_tokens_used", 0)
                + settlement_recommendation.pop("_tokens_used", 0)
            )
            summary_text = (
                f"Total award: ₹{compensation_breakdown.get('total_award', 0):,}. "
                f"Settlement {'recommended' if settlement_recommendation.get('settlement_recommended') else 'not recommended'}."
            )
            await self._complete_stage(stage5, context, summary_text, session)
        except Exception as e:
            await self._fail_stage(stage5, str(e), session)
            raise

        # ── STAGE 6: Quality Assurance ───────────────────────────────────
        stage6 = await self._start_stage(case_id, 6, "quality_assurance", "BiasConflictAgent", session)
        try:
            loop = asyncio.get_running_loop()
            bias_report = await loop.run_in_executor(None, lambda: BiasConflictAgent().analyze(context))
            context["bias_report"] = bias_report
            total_tokens += bias_report.pop("_tokens_used", 0)
            summary_text = (
                f"Bias score: {bias_report.get('overall_bias_score', '?')}. "
                f"Neutrality check: {'PASSED' if bias_report.get('passed') else 'FLAGGED'}. "
                f"Flags: {len(bias_report.get('flags', []))}."
            )
            await self._complete_stage(stage6, context, summary_text, session)
        except Exception as e:
            await self._fail_stage(stage6, str(e), session)
            raise

        # ── STAGE 7: Final Verdict ───────────────────────────────────────
        stage7 = await self._start_stage(case_id, 7, "final_verdict", "ChiefJudgeAgent", session)
        try:
            loop = asyncio.get_running_loop()
            final_verdict = await loop.run_in_executor(None, lambda: ChiefJudgeAgent().deliberate(context))
            context["final_verdict"] = final_verdict
            total_tokens += final_verdict.pop("_tokens_used", 0)

            # Post-verdict grounding verification
            citation_tracker = CitationTracker()
            grounding_report = citation_tracker.verify_grounding(
                final_verdict,
                context.get("evidence_chunks", []),
            )

            summary_text = (
                f"VERDICT: {final_verdict.get('verdict', '?')}. "
                f"Confidence: {final_verdict.get('confidence_score', '?')}. "
                f"Grounding: {grounding_report.overall_score:.2f}."
            )
            await self._complete_stage(stage7, context, summary_text, session)

            total_duration_ms = int((time.time() - t_start) * 1000)

            await _broadcast(case_id, "verdict_ready", {
                "verdict": final_verdict.get("verdict"),
                "confidence": final_verdict.get("confidence_score"),
            })

            return {
                "final_verdict": final_verdict,
                "grounding_report": grounding_report.to_dict(),
                "bias_report": context.get("bias_report", {}),
                "settlement_recommendation": context.get("settlement_recommendation", {}),
                "compensation_breakdown": context.get("compensation_breakdown", {}),
                "total_groq_tokens": total_tokens,
                "total_duration_ms": total_duration_ms,
                "claimant_summary": context.get("claimant_summary", {}),
                "respondent_summary": context.get("respondent_summary", {}),
            }

        except Exception as e:
            await self._fail_stage(stage7, str(e), session)
            raise

    async def _start_stage(
        self,
        case_id: str,
        stage_number: int,
        stage_name: str,
        agent_name: str,
        session: AsyncSession,
    ) -> ArbitrationStage:
        stage = ArbitrationStage(
            case_id=case_id,
            stage_number=stage_number,
            stage_name=stage_name,
            agent_name=agent_name,
            status=StageStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )
        session.add(stage)
        await session.commit()
        await session.refresh(stage)

        await _broadcast(case_id, "stage_started", {
            "stage_number": stage_number,
            "stage_name": stage_name,
            "message": f"Starting {stage_name}...",
        })

        logger.info("stage_started", extra={"case_id": case_id, "stage": stage_name})
        return stage

    async def _complete_stage(
        self,
        stage: ArbitrationStage,
        context: dict,
        summary: str,
        session: AsyncSession,
    ) -> None:
        now = datetime.now(timezone.utc)
        duration_ms = int((now - stage.started_at).total_seconds() * 1000) if stage.started_at else 0
        stage.status = StageStatus.COMPLETED
        stage.completed_at = now
        stage.duration_ms = duration_ms
        stage.output_summary = summary
        # Store lightweight context (avoid storing huge docs)
        safe_context = {k: v for k, v in context.items() if k not in ("claimant_docs", "respondent_docs", "evidence_chunks")}
        try:
            stage.output_json = json.loads(json.dumps(safe_context, default=str))
        except Exception:
            stage.output_json = {}
        await session.commit()

        await _broadcast(stage.case_id, "stage_completed", {
            "stage_number": stage.stage_number,
            "stage_name": stage.stage_name,
            "summary": summary,
            "duration_ms": duration_ms,
        })

        logger.info("stage_completed", extra={
            "case_id": stage.case_id,
            "stage": stage.stage_name,
            "duration_ms": duration_ms,
        })

    async def _fail_stage(
        self,
        stage: ArbitrationStage,
        error: str,
        session: AsyncSession,
    ) -> None:
        stage.status = StageStatus.FAILED
        stage.error_message = error[:500]
        stage.completed_at = datetime.now(timezone.utc)
        await session.commit()

        await _broadcast(stage.case_id, "stage_failed", {
            "stage_number": stage.stage_number,
            "stage_name": stage.stage_name,
            "error": error[:200],
        })

        logger.error("stage_failed", extra={
            "case_id": stage.case_id,
            "stage": stage.stage_name,
            "error": error,
        })
