"""
Witness Consistency Agent — checks if each party's own documents are internally consistent.
"""
from __future__ import annotations
import json
import logging
from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

SYSTEM = """You are a document consistency analyst in Indian civil arbitration.
Your task: Check if a single party's own documents contradict each other internally.

Look for:
1. Date inconsistencies (different dates for same event)
2. Amount discrepancies (different amounts for same payment/contract)
3. Timeline gaps (events out of sequence)
4. Contradictory statements within same party's documents
5. Missing signatures, incomplete clauses

Return ONLY valid JSON:
{
  "party": "CLAIMANT | RESPONDENT",
  "internal_contradictions": [
    {
      "issue": "Description of contradiction",
      "document_1": "First document/section",
      "document_2": "Second document/section",
      "severity": "HIGH | MEDIUM | LOW"
    }
  ],
  "timeline_issues": ["Issue 1", "Issue 2"],
  "consistency_score": 0.85,
  "credibility_impact": "HIGH | MEDIUM | LOW",
  "summary": "Brief summary of consistency analysis"
}"""


class WitnessConsistencyAgent(BaseAgent):
    name = "witness_consistency_agent"
    max_tokens = 2000

    def check_consistency(self, party: str, documents_text: str) -> dict:
        doc_text = documents_text[:8000]
        messages = [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Analyze internal consistency of {party}'s documents:\n\n"
                    f"DOCUMENTS:\n{doc_text}"
                ),
            },
        ]

        text, tokens = self._chat(messages, json_mode=True)
        result = self._parse_json(text, fallback={"party": party, "consistency_score": 0.5})
        result["party"] = party
        result["_tokens_used"] = tokens
        return result
