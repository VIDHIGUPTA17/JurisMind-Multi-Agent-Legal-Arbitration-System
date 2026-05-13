"""
Legal Argument Generation Agent — identifies applicable Indian laws and constructs arguments.
"""
from __future__ import annotations
import json
import logging
from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

SYSTEM = """You are a senior Indian civil law expert in arbitration proceedings.
Your task: For each disputed fact, identify applicable Indian statutes and construct legal arguments for BOTH sides.

Indian statutes to consider:
- Indian Contract Act 1872 (Sections 10, 17, 23, 73, 74, 75)
- Arbitration and Conciliation Act 1996
- Specific Relief Act 1963
- Transfer of Property Act 1882
- Consumer Protection Act 2019
- Companies Act 2013
- Sale of Goods Act 1930
- Indian Evidence Act 1872

Return ONLY valid JSON:
{
  "legal_issues": [
    {
      "issue": "Legal issue to be determined",
      "applicable_law": "Specific Act and Section",
      "claimant_argument": "Legal argument for claimant citing statute",
      "respondent_argument": "Legal argument for respondent citing statute",
      "burden_of_proof": "CLAIMANT | RESPONDENT",
      "evidence_weight": "STRONG | MODERATE | WEAK",
      "legal_precedent": "Relevant Indian case law if applicable or null"
    }
  ],
  "primary_cause_of_action": "Main legal claim",
  "secondary_causes": ["Secondary claim 1"],
  "jurisdiction_note": "Indian Arbitration and Conciliation Act 1996 applies"
}"""


class LegalArgumentAgent(BaseAgent):
    name = "legal_argument_agent"
    max_tokens = 4000

    def generate_arguments(
        self,
        contradiction_report: dict,
        evidence_map: dict,
        claimant_summary: dict,
        respondent_summary: dict,
    ) -> dict:
        messages = [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": (
                    f"DISPUTED FACTS:\n{json.dumps(contradiction_report.get('disputed_facts', []), indent=2)[:2000]}\n\n"
                    f"CLAIMANT POSITION:\n{json.dumps(claimant_summary, indent=2)[:2000]}\n\n"
                    f"RESPONDENT POSITION:\n{json.dumps(respondent_summary, indent=2)[:2000]}\n\n"
                    f"EVIDENCE MAP:\n{json.dumps(evidence_map, indent=2)[:1500]}"
                ),
            },
        ]

        text, tokens = self._chat(messages, json_mode=True)
        result = self._parse_json(text, fallback={"legal_issues": []})
        result["_tokens_used"] = tokens
        return result
