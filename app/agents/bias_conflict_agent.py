"""
Bias / Conflict Analysis Agent — checks if reasoning is neutral and balanced.
"""
from __future__ import annotations
import json
import logging
from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

SYSTEM = """You are a neutrality and bias detection expert in legal proceedings.
Your task: Review the entire arbitration analysis for bias or unfairness.

Check for:
1. Evidence imbalance: Did analysis use more evidence from one party?
2. Argumentative bias: Were both sides' arguments fully considered?
3. Compensation justification: Is the award within reasonable range?
4. Circular reasoning: Does conclusion assume what it's supposed to prove?
5. Consistency: Are similar facts treated consistently?

Return ONLY valid JSON:
{
  "overall_bias_score": 0.12,
  "bias_level": "MINIMAL | LOW | MODERATE | HIGH",
  "evidence_balance": {
    "claimant_evidence_cited": 8,
    "respondent_evidence_cited": 6,
    "balance_ratio": 0.75,
    "balanced": true
  },
  "flags": [
    {
      "type": "EVIDENCE_IMBALANCE | ARGUMENT_IGNORED | CIRCULAR_REASONING | OTHER",
      "description": "Description of the flag",
      "severity": "HIGH | MEDIUM | LOW"
    }
  ],
  "compensation_in_range": true,
  "compensation_note": "Award appears reasonable given the evidence",
  "overall_fairness_assessment": "The analysis appears balanced and neutral",
  "passed": true,
  "recommendation": "No changes needed | Suggested adjustment"
}"""


class BiasConflictAgent(BaseAgent):
    name = "bias_conflict_agent"
    max_tokens = 2000

    def analyze(self, pipeline_context: dict) -> dict:
        """
        pipeline_context: accumulated outputs from all previous stages.
        """
        summary = {
            "claimant_strength": pipeline_context.get("claimant_summary", {}).get("overall_strength_assessment"),
            "respondent_strength": pipeline_context.get("respondent_summary", {}).get("overall_strength_assessment"),
            "liability": pipeline_context.get("liability_determination", {}).get("primary_liability"),
            "liability_split": pipeline_context.get("liability_determination", {}).get("liability_split"),
            "total_award": pipeline_context.get("compensation_breakdown", {}).get("total_award"),
            "disputed_facts_count": len(pipeline_context.get("contradiction_report", {}).get("disputed_facts", [])),
            "settlement_recommended": pipeline_context.get("settlement_recommendation", {}).get("settlement_recommended"),
            "claimant_claims_count": len(pipeline_context.get("claimant_summary", {}).get("claims", [])),
            "respondent_defences_count": len(pipeline_context.get("respondent_summary", {}).get("defences", [])),
        }

        messages = [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": (
                    f"ARBITRATION ANALYSIS SUMMARY:\n{json.dumps(summary, indent=2)}\n\n"
                    f"LEGAL ISSUES:\n{json.dumps(pipeline_context.get('legal_analysis', {}).get('legal_issues', []), indent=2)[:2000]}\n\n"
                    f"EVIDENCE MAP COUNTS:\n"
                    f"Supported: {pipeline_context.get('evidence_map', {}).get('supported_count', 0)}, "
                    f"Not Found: {pipeline_context.get('evidence_map', {}).get('not_found_count', 0)}, "
                    f"Contradicted: {pipeline_context.get('evidence_map', {}).get('contradicted_count', 0)}"
                ),
            },
        ]

        text, tokens = self._chat(messages, json_mode=True)
        result = self._parse_json(text, fallback={"overall_bias_score": 0.5, "passed": True, "flags": []})
        result["_tokens_used"] = tokens
        return result
