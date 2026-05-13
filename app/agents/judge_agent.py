"""
JudgeAgent — delivers an impartial verdict under Indian civil law.

Uses Groq tool-use to call retrieve_relevant_chunks (pgvector RAG)
up to 3 times to gather additional context before issuing a verdict.

The judge NEVER receives raw PII — only anonymized text.
"""
import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base_agent import BaseAgent
from app.rag.retriever import retrieve_relevant_chunks

logger = logging.getLogger(__name__)

JUDGE_SYSTEM = """You are an impartial AI arbitrator adjudicating a civil dispute under the Indian legal framework.

Applicable statutes you MUST consider:
- Arbitration and Conciliation Act, 1996
- Indian Contract Act, 1872
- Transfer of Property Act, 1882
- Consumer Protection Act, 2019
- Specific Relief Act, 1963
- Sale of Goods Act, 1930 (where applicable)
- Information Technology Act, 2000 (where applicable)

Your role:
1. Review the claimant's case summary and the respondent's defence summary.
2. Use the retrieve_relevant_chunks tool to fetch additional evidence from the case documents (you may call it up to 3 times with different queries).
3. Apply the relevant statutes to the facts.
4. Deliver a reasoned, impartial verdict.

ALL text has been anonymised — PII replaced with tokens like [PERSON_1], [AADHAAR_1].
Do NOT attempt to de-anonymise or speculate about real identities.

After gathering enough evidence, output valid JSON ONLY (no markdown, no extra text):
{
  "applicable_laws": ["Act name — Section X: brief relevance"],
  "claimant_position": "...",
  "respondent_position": "...",
  "key_issues": ["..."],
  "reasoning": "...",
  "verdict": "IN FAVOUR OF CLAIMANT | IN FAVOUR OF RESPONDENT | PARTIAL AWARD | DISMISSED",
  "relief_awarded": "...",
  "costs": "..."
}"""

RETRIEVE_TOOL = {
    "type": "function",
    "function": {
        "name": "retrieve_relevant_chunks",
        "description": (
            "Search the case documents for passages relevant to a legal query. "
            "Use this to gather specific evidence before deciding. "
            "Call up to 3 times with different targeted queries."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A specific legal or factual query to search for in the case documents.",
                }
            },
            "required": ["query"],
        },
    },
}


class JudgeAgent(BaseAgent):

    async def deliberate(
        self,
        case_id: str,
        claimant_summary: dict,
        respondent_summary: dict,
        session: AsyncSession,
    ) -> dict:
        """
        Run the full judge deliberation:
        1. Provide claimant + respondent summaries
        2. Tool-use loop: retrieve relevant chunks (up to 3 rounds)
        3. Return structured verdict dict

        NEVER receives raw PII.
        """
        messages = [
            {"role": "system", "content": JUDGE_SYSTEM},
            {
                "role": "user",
                "content": (
                    "CLAIMANT SUMMARY:\n"
                    + json.dumps(claimant_summary, indent=2)
                    + "\n\nRESPONDENT SUMMARY:\n"
                    + json.dumps(respondent_summary, indent=2)
                    + "\n\nBegin your deliberation. Use the retrieve_relevant_chunks tool as needed, "
                    "then issue your final verdict in the specified JSON format."
                ),
            },
        ]

        tool_call_count = 0
        max_tool_calls = 3

        while True:
            use_tools = tool_call_count < max_tool_calls
            response = self._chat(
                messages,
                tools=[RETRIEVE_TOOL] if use_tools else None,
                tool_choice="auto" if use_tools else None,
                json_mode=not use_tools,  # JSON mode only on final call
                max_tokens=4096,
            )

            choice = response.choices[0]
            finish_reason = choice.finish_reason

            if finish_reason == "tool_calls":
                # Process tool calls
                tool_calls = choice.message.tool_calls
                # Append assistant message with tool_calls
                messages.append({"role": "assistant", "content": choice.message.content, "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in tool_calls
                ]})

                for tc in tool_calls:
                    tool_call_count += 1
                    args = json.loads(tc.function.arguments)
                    query = args.get("query", "")
                    logger.info("Judge tool call #%d: retrieve_relevant_chunks(query=%r)", tool_call_count, query)

                    chunks = await retrieve_relevant_chunks(query=query, case_id=case_id, session=session)
                    chunks_text = "\n\n".join(
                        f"[Chunk {i+1} — similarity {c.get('similarity', 0):.3f}]\n{c['chunk_text']}"
                        for i, c in enumerate(chunks)
                    )
                    if not chunks_text:
                        chunks_text = "No relevant chunks found for this query."

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": chunks_text,
                    })

                if tool_call_count >= max_tool_calls:
                    # Force final answer — no more tools
                    messages.append({
                        "role": "user",
                        "content": "You have used the maximum number of retrieval calls. Now deliver your final verdict in JSON.",
                    })
            else:
                # stop or end_turn — parse final JSON verdict
                return self._parse_json_response(response)
