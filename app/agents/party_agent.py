"""
Party Agent — represents claimant or respondent.
Enhanced with citation-required output (every claim must cite evidence).
"""
from __future__ import annotations
import json
import logging
from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

CLAIMANT_SYSTEM = """You are a legal representative for the CLAIMANT in an Indian civil arbitration.
Your task: Analyze the claimant's documents and produce a structured case summary.

CRITICAL RULES:
1. ONLY state facts that are explicitly present in the provided documents.
2. For EVERY claim or fact, cite the evidence: "As per [document section/page], ..."
3. Do NOT invent facts, dates, amounts, or names not in the documents.
4. Apply Indian law framework: Indian Contract Act 1872, Arbitration and Conciliation Act 1996, etc.

Return ONLY valid JSON with this structure:
{
  "role": "CLAIMANT",
  "claims": [
    {
      "claim": "Brief statement of the claim",
      "evidence_basis": "Quote from documents or 'No direct evidence'",
      "strength": "STRONG | MODERATE | WEAK"
    }
  ],
  "key_facts": ["fact 1 with source", "fact 2 with source"],
  "relief_sought": "Specific relief requested (with amounts if stated in docs)",
  "applicable_laws_suggested": ["ICA 1872 §73", "Arbitration Act 1996"],
  "overall_strength_assessment": "STRONG | MODERATE | WEAK",
  "documents_summary": "Brief summary of what documents were provided"
}"""

RESPONDENT_SYSTEM = """You are a legal representative for the RESPONDENT in an Indian civil arbitration.
Your task: Analyze the respondent's documents and produce a structured defence summary.

CRITICAL RULES:
1. ONLY state defences that are explicitly present in the provided documents.
2. For EVERY defence, cite the evidence: "As per [document section/page], ..."
3. Do NOT invent facts, dates, amounts, or names not in the documents.
4. Apply Indian law framework.

Return ONLY valid JSON with this structure:
{
  "role": "RESPONDENT",
  "defences": [
    {
      "defence": "Brief statement of the defence",
      "evidence_basis": "Quote from documents or 'No direct evidence'",
      "strength": "STRONG | MODERATE | WEAK"
    }
  ],
  "counter_claims": ["counter-claim 1 with source", "counter-claim 2 with source"],
  "key_facts": ["fact 1 with source", "fact 2 with source"],
  "applicable_laws_suggested": ["ICA 1872 §73"],
  "overall_strength_assessment": "STRONG | MODERATE | WEAK",
  "documents_summary": "Brief summary of what documents were provided"
}"""


class PartyAgent(BaseAgent):
    name = "party_agent"
    max_tokens = 3000

    def summarise(self, role: str, documents_text: str) -> dict:
        """
        Produce a structured summary of one party's position.
        role: "CLAIMANT" or "RESPONDENT"
        documents_text: concatenated anonymized document text
        """
        system = CLAIMANT_SYSTEM if role == "CLAIMANT" else RESPONDENT_SYSTEM

        if not documents_text or not documents_text.strip():
            return {
                "role": role,
                "claims" if role == "CLAIMANT" else "defences": [],
                "key_facts": [],
                "overall_strength_assessment": "WEAK",
                "documents_summary": "No documents provided",
            }

        # Truncate to avoid token limits
        doc_text = documents_text[:12000]

        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": (
                    f"Analyze the following {role} documents and produce the structured summary:\n\n"
                    f"DOCUMENTS:\n{doc_text}"
                ),
            },
        ]

        text, tokens = self._chat(messages, json_mode=True)
        result = self._parse_json(text, fallback={"role": role, "error": "parse_failed"})
        result["_tokens_used"] = tokens

        logger.info("party_agent_completed", extra={
            "role": role,
            "tokens": tokens,
            "strength": result.get("overall_strength_assessment", "?"),
        })
        return result
