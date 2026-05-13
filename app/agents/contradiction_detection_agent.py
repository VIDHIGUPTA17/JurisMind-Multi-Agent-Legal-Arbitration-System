"""
Contradiction Detection Agent — finds contradictions between party positions.
"""
from __future__ import annotations
import json
import logging
from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

SYSTEM = """You are a contradiction detection specialist in Indian civil arbitration.
Your task: Identify contradictions and agreements between the two parties' positions.

Analyze both party summaries and the evidence map to find:
1. Facts BOTH parties agree on (agreed facts)
2. Direct contradictions between party positions
3. Claims made by only one party (uncontested)
4. Categorize disputes: FACTUAL (different facts), LEGAL (different interpretation), MIXED

Return ONLY valid JSON:
{
  "agreed_facts": ["Both parties agree that...", "..."],
  "disputed_facts": [
    {
      "issue": "Brief description of the dispute",
      "claimant_says": "Claimant's position",
      "respondent_says": "Respondent's position",
      "evidence_supports": "CLAIMANT | RESPONDENT | BOTH | NEITHER",
      "dispute_type": "FACTUAL | LEGAL | MIXED",
      "severity": "HIGH | MEDIUM | LOW"
    }
  ],
  "unilateral_claims": [
    {
      "party": "CLAIMANT | RESPONDENT",
      "claim": "The claim not addressed by other party",
      "unchallenged": true
    }
  ],
  "contradiction_count": 0,
  "agreed_fact_count": 0
}"""


class ContradictionDetectionAgent(BaseAgent):
    name = "contradiction_detection_agent"
    max_tokens = 3000

    def detect(
        self,
        claimant_summary: dict,
        respondent_summary: dict,
        evidence_map: dict,
    ) -> dict:
        messages = [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": (
                    f"CLAIMANT SUMMARY:\n{json.dumps(claimant_summary, indent=2)[:3000]}\n\n"
                    f"RESPONDENT SUMMARY:\n{json.dumps(respondent_summary, indent=2)[:3000]}\n\n"
                    f"EVIDENCE MAP:\n{json.dumps(evidence_map, indent=2)[:2000]}"
                ),
            },
        ]

        text, tokens = self._chat(messages, json_mode=True)
        result = self._parse_json(text, fallback={"disputed_facts": [], "agreed_facts": []})
        result["_tokens_used"] = tokens
        return result
