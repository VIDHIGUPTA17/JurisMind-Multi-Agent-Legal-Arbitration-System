"""
Liability Reasoning Agent — determines liability per legal issue.
"""
from __future__ import annotations
import json
import logging
from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

SYSTEM = """You are a liability determination expert in Indian civil arbitration.
Your task: For each legal issue, determine which party bears liability and to what degree.

Apply legal tests:
- Reasonable person test
- But-for causation (but for the act, would harm have occurred?)
- Proximate cause (is the breach the direct cause of loss?)
- Contributory negligence (did claimant contribute to loss?)

Return ONLY valid JSON:
{
  "primary_liability": "CLAIMANT | RESPONDENT | SHARED",
  "liability_split": {
    "claimant_percent": 20,
    "respondent_percent": 80
  },
  "breach_type": "MATERIAL | MINOR | ANTICIPATORY | FUNDAMENTAL",
  "breach_severity": "HIGH | MEDIUM | LOW",
  "causation_established": true,
  "reasoning_per_issue": [
    {
      "issue": "Legal issue",
      "liability": "CLAIMANT | RESPONDENT | SHARED",
      "legal_test_applied": "But-for causation",
      "reasoning": "Explanation of determination"
    }
  ],
  "mitigating_factors": ["Factor 1 reducing liability"],
  "aggravating_factors": ["Factor 1 increasing liability"],
  "summary": "Overall liability determination summary"
}"""


class LiabilityReasoningAgent(BaseAgent):
    name = "liability_reasoning_agent"
    max_tokens = 3000

    def determine_liability(
        self,
        legal_analysis: dict,
        contradiction_report: dict,
    ) -> dict:
        messages = [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": (
                    f"LEGAL ISSUES AND ARGUMENTS:\n{json.dumps(legal_analysis.get('legal_issues', []), indent=2)[:3000]}\n\n"
                    f"DISPUTED FACTS:\n{json.dumps(contradiction_report.get('disputed_facts', []), indent=2)[:2000]}\n\n"
                    f"AGREED FACTS:\n{json.dumps(contradiction_report.get('agreed_facts', []), indent=2)[:1000]}"
                ),
            },
        ]

        text, tokens = self._chat(messages, json_mode=True)
        result = self._parse_json(text, fallback={"primary_liability": "SHARED", "liability_split": {"claimant_percent": 50, "respondent_percent": 50}})
        result["_tokens_used"] = tokens
        return result
