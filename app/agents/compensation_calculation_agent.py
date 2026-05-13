"""
Compensation Calculation Agent — calculates structured damages award.
"""
from __future__ import annotations
import json
import logging
from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

SYSTEM = """You are a compensation calculation expert in Indian civil arbitration.
Your task: Calculate a structured compensation award based on liability determination and evidence of damages.

Compensation framework (Indian law):
- Compensatory damages: Actual loss proved by evidence (Section 73 ICA 1872)
- Consequential damages: Loss that was in reasonable contemplation
- Interest: Per RBI rates (typically 6-12% per annum)
- Deductions: Contributory negligence percentage
- Litigation costs: Reasonable costs of arbitration

IMPORTANT: Only award damages that are:
1. Proved by evidence (not speculative)
2. Quantifiable (specific amounts)
3. Causally linked to the breach

Return ONLY valid JSON:
{
  "compensatory_damages": 500000,
  "compensatory_basis": "Explanation of how calculated from evidence",
  "consequential_damages": 50000,
  "consequential_basis": "Explanation or null if not applicable",
  "interest_rate_percent": 9,
  "interest_period": "From [date] to date of award",
  "interest_amount": 45000,
  "deductions": {
    "contributory_negligence_percent": 20,
    "deduction_amount": 109000,
    "reason": "Reason for deduction"
  },
  "litigation_costs": 25000,
  "total_award": 511000,
  "currency": "INR",
  "calculation_methodology": "Step-by-step calculation",
  "award_confidence": "HIGH | MEDIUM | LOW",
  "notes": "Any caveats or limitations"
}"""


class CompensationCalculationAgent(BaseAgent):
    name = "compensation_calculation_agent"
    max_tokens = 3000

    def calculate(
        self,
        liability_determination: dict,
        evidence_chunks: list[dict],
        claimant_summary: dict,
    ) -> dict:
        evidence_text = "\n".join([
            c.get("chunk_text", "")[:200] for c in evidence_chunks[:10]
        ])

        messages = [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": (
                    f"LIABILITY DETERMINATION:\n{json.dumps(liability_determination, indent=2)[:2000]}\n\n"
                    f"CLAIMANT'S RELIEF SOUGHT:\n{claimant_summary.get('relief_sought', 'Not specified')}\n\n"
                    f"EVIDENCE OF DAMAGES:\n{evidence_text}"
                ),
            },
        ]

        text, tokens = self._chat(messages, json_mode=True)
        result = self._parse_json(text, fallback={"total_award": 0, "currency": "INR", "award_confidence": "LOW"})
        result["_tokens_used"] = tokens
        return result
