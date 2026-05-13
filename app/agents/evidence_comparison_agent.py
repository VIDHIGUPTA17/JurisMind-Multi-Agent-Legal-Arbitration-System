"""
Evidence Comparison Agent — cross-references party claims against actual document chunks.
"""
from __future__ import annotations
import json
import logging
from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

SYSTEM = """You are an evidence analysis expert in Indian civil arbitration.
Your task: Cross-reference claims from BOTH parties against actual evidence chunks.

For each claim from either party, determine:
- "SUPPORTED": Found in the evidence chunks (cite which chunk)
- "NOT_FOUND": Not found in any evidence chunk
- "CONTRADICTED": Evidence chunks say the opposite

Return ONLY valid JSON:
{
  "claimant_evidence_map": [
    {
      "claim": "The claimant's claim",
      "status": "SUPPORTED | NOT_FOUND | CONTRADICTED",
      "evidence_reference": "Quote from evidence chunk or null",
      "confidence": "HIGH | MEDIUM | LOW"
    }
  ],
  "respondent_evidence_map": [
    {
      "claim": "The respondent's claim/defence",
      "status": "SUPPORTED | NOT_FOUND | CONTRADICTED",
      "evidence_reference": "Quote from evidence chunk or null",
      "confidence": "HIGH | MEDIUM | LOW"
    }
  ],
  "total_claims_analyzed": 0,
  "supported_count": 0,
  "not_found_count": 0,
  "contradicted_count": 0
}"""


class EvidenceComparisonAgent(BaseAgent):
    name = "evidence_comparison_agent"
    max_tokens = 3000

    def compare(
        self,
        claimant_summary: dict,
        respondent_summary: dict,
        evidence_chunks: list[dict],
    ) -> dict:
        evidence_text = "\n\n".join([
            f"[Chunk {i+1}] {c.get('chunk_text', '')[:300]}"
            for i, c in enumerate(evidence_chunks[:15])
        ])

        claimant_claims = claimant_summary.get("claims", [])
        respondent_defences = respondent_summary.get("defences", [])

        messages = [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": (
                    f"CLAIMANT CLAIMS:\n{json.dumps(claimant_claims, indent=2)}\n\n"
                    f"RESPONDENT DEFENCES:\n{json.dumps(respondent_defences, indent=2)}\n\n"
                    f"EVIDENCE CHUNKS:\n{evidence_text}"
                ),
            },
        ]

        text, tokens = self._chat(messages, json_mode=True)
        result = self._parse_json(text, fallback={"error": "parse_failed"})
        result["_tokens_used"] = tokens
        return result
