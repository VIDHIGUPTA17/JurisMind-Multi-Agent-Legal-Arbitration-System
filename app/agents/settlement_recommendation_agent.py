"""
Settlement Recommendation Agent — assesses if mediated settlement would be better.
"""
from __future__ import annotations
import json
import logging
from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

SYSTEM = """You are a dispute resolution specialist in Indian civil arbitration.
Your task: Assess whether a mediated settlement would be appropriate and beneficial.

Consider:
- Liability split (if not 100% one-sided, settlement may be better)
- Legal costs both parties will incur
- Time to enforce an award
- Ongoing business relationship (if relevant)
- Uncertainty of litigation

Return ONLY valid JSON:
{
  "settlement_recommended": true,
  "recommendation_strength": "STRONG | MODERATE | WEAK",
  "recommended_settlement_range": {
    "minimum_inr": 350000,
    "maximum_inr": 550000,
    "midpoint_inr": 450000
  },
  "rationale": "Explanation of why settlement is/is not recommended",
  "compromise_points": [
    "Point where each party could concede",
    "Another compromise point"
  ],
  "benefits_of_settlement": [
    "Saves litigation costs of approx ₹X",
    "Faster resolution"
  ],
  "risks_of_rejecting_settlement": [
    "Risk 1 if parties proceed to full arbitration"
  ],
  "settlement_conditions": [
    "Suggested condition 1"
  ]
}"""


class SettlementRecommendationAgent(BaseAgent):
    name = "settlement_recommendation_agent"
    max_tokens = 2000

    def recommend(
        self,
        liability_determination: dict,
        compensation_breakdown: dict,
    ) -> dict:
        messages = [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": (
                    f"LIABILITY DETERMINATION:\n{json.dumps(liability_determination, indent=2)[:2000]}\n\n"
                    f"COMPENSATION BREAKDOWN:\n{json.dumps(compensation_breakdown, indent=2)[:2000]}"
                ),
            },
        ]

        text, tokens = self._chat(messages, json_mode=True)
        result = self._parse_json(text, fallback={"settlement_recommended": False, "recommendation_strength": "WEAK"})
        result["_tokens_used"] = tokens
        return result
