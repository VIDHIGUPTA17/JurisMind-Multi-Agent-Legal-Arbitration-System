"""
Chief Judge Agent — synthesizes all specialist agent outputs into a final verdict.
"""
from __future__ import annotations
import json
import logging
from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

CHIEF_JUDGE_SYSTEM = """You are the Chief Arbitrator in an Indian civil dispute, governed by the Arbitration and Conciliation Act 1996.

You have received comprehensive analysis from 8 specialist agents. Your task: Synthesize all inputs into a FINAL, BINDING ARBITRATION AWARD.

The award must:
1. Address each legal issue with a clear determination
2. Cite specific evidence by document and section
3. Reference applicable Indian statutes with section numbers
4. Provide clear compensation award with calculation
5. Include settlement recommendation if applicable
6. Be defensible, neutral, and grounded in evidence

Return ONLY valid JSON:
{
  "verdict": "IN FAVOUR OF CLAIMANT | IN FAVOUR OF RESPONDENT | PARTIAL AWARD | DISMISSED",
  "verdict_summary": "One sentence summary of the outcome",
  "applicable_laws": [
    "Indian Contract Act 1872, Section 73",
    "Arbitration and Conciliation Act 1996, Section 34"
  ],
  "key_issues_determined": [
    {
      "issue": "Was there a valid and binding contract?",
      "determination": "YES - contract established by documentary evidence",
      "evidence_basis": "Contract.pdf, Clause 1.1",
      "law_applied": "ICA 1872, Section 10"
    }
  ],
  "reasoning": "Comprehensive multi-paragraph reasoning covering facts, law, and evidence",
  "liability_determination": "RESPONDENT liable for material breach",
  "relief_awarded": {
    "type": "MONETARY | SPECIFIC_PERFORMANCE | INJUNCTION | NONE",
    "amount_inr": 500000,
    "description": "Compensatory damages for breach of contract",
    "interest": "9% per annum from date of breach",
    "costs": "Litigation costs of ₹25,000 awarded to claimant"
  },
  "settlement_note": "Settlement was/was not recommended (refer to settlement analysis)",
  "bias_attestation": "This award was reviewed for neutrality. Bias score: 0.12/1.0 (MINIMAL)",
  "confidence_score": 0.82,
  "dissenting_note": null,
  "award_date": "To be filled by system",
  "arbitrator": "AI Chief Arbitrator (Legal Arbitration System v2)"
}"""


class ChiefJudgeAgent(BaseAgent):
    name = "chief_judge_agent"
    max_tokens = 5000

    def deliberate(self, pipeline_context: dict) -> dict:
        """
        Synthesize all specialist agent outputs into a final verdict.
        pipeline_context: accumulated dict from all 6 previous stages.
        """
        # Build a structured summary of all stage outputs for the judge
        context_summary = {
            "claimant_position": {
                "strength": pipeline_context.get("claimant_summary", {}).get("overall_strength_assessment"),
                "claims": pipeline_context.get("claimant_summary", {}).get("claims", [])[:5],
                "relief_sought": pipeline_context.get("claimant_summary", {}).get("relief_sought"),
            },
            "respondent_position": {
                "strength": pipeline_context.get("respondent_summary", {}).get("overall_strength_assessment"),
                "defences": pipeline_context.get("respondent_summary", {}).get("defences", [])[:5],
            },
            "evidence_analysis": {
                "supported_claims": pipeline_context.get("evidence_map", {}).get("supported_count", 0),
                "not_found": pipeline_context.get("evidence_map", {}).get("not_found_count", 0),
                "contradicted": pipeline_context.get("evidence_map", {}).get("contradicted_count", 0),
            },
            "agreed_facts": pipeline_context.get("contradiction_report", {}).get("agreed_facts", []),
            "disputed_facts": pipeline_context.get("contradiction_report", {}).get("disputed_facts", [])[:5],
            "legal_issues": pipeline_context.get("legal_analysis", {}).get("legal_issues", [])[:5],
            "liability": pipeline_context.get("liability_determination", {}),
            "compensation": pipeline_context.get("compensation_breakdown", {}),
            "settlement": pipeline_context.get("settlement_recommendation", {}),
            "bias_check": {
                "score": pipeline_context.get("bias_report", {}).get("overall_bias_score", 0),
                "passed": pipeline_context.get("bias_report", {}).get("passed", True),
                "flags": pipeline_context.get("bias_report", {}).get("flags", []),
            },
            "claimant_consistency": pipeline_context.get("claimant_consistency", {}).get("consistency_score"),
            "respondent_consistency": pipeline_context.get("respondent_consistency", {}).get("consistency_score"),
        }

        messages = [
            {"role": "system", "content": CHIEF_JUDGE_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"COMPLETE ARBITRATION ANALYSIS:\n{json.dumps(context_summary, indent=2)[:8000]}\n\n"
                    "Based on all specialist agent analyses, issue the final arbitration award."
                ),
            },
        ]

        text, tokens = self._chat(messages, json_mode=True)
        result = self._parse_json(text, fallback={
            "verdict": "PARTIAL AWARD",
            "reasoning": "Could not generate full verdict.",
            "confidence_score": 0.3,
        })
        result["_tokens_used"] = tokens

        logger.info("chief_judge_deliberated", extra={
            "verdict": result.get("verdict"),
            "confidence": result.get("confidence_score"),
            "tokens": tokens,
        })
        return result
