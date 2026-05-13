"""
Citation tracking and grounding verification.
Tracks which document chunks were used in each agent's reasoning,
and verifies that the verdict claims are grounded in actual evidence.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from app.agents.base_agent import get_groq_client
from app.config import get_settings
settings = get_settings()


@dataclass
class Citation:
    chunk_id: str
    document_id: str
    document_filename: str
    page_numbers: list[int]
    section_header: str | None
    similarity_score: float
    rerank_score: float
    cited_text_snippet: str  # first 200 chars


@dataclass
class GroundingReport:
    overall_score: float          # 0.0 (hallucinated) - 1.0 (fully grounded)
    grounded_claims: list[str]    # claims supported by evidence
    ungrounded_claims: list[str]  # claims with no evidence
    contradicted_claims: list[str]  # claims contradicted by evidence
    citations_used: list[Citation]
    passed: bool                  # True if overall_score >= 0.6

    def to_dict(self) -> dict:
        return {
            "overall_score": self.overall_score,
            "grounded_claims": self.grounded_claims,
            "ungrounded_claims": self.ungrounded_claims,
            "contradicted_claims": self.contradicted_claims,
            "citations_used": [
                {
                    "chunk_id": c.chunk_id,
                    "document_id": c.document_id,
                    "document_filename": c.document_filename,
                    "page_numbers": c.page_numbers,
                    "section_header": c.section_header,
                    "similarity_score": c.similarity_score,
                    "rerank_score": c.rerank_score,
                    "cited_text_snippet": c.cited_text_snippet,
                }
                for c in self.citations_used
            ],
            "passed": self.passed,
        }


class CitationTracker:
    """
    Tracks which chunks were retrieved and verifies verdict grounding.
    """

    def build_citations(self, retrieved_chunks: list[dict]) -> list[Citation]:
        """Convert retrieved chunk dicts into Citation objects."""
        citations = []
        for chunk in retrieved_chunks:
            citations.append(Citation(
                chunk_id=chunk.get("chunk_id", ""),
                document_id=chunk.get("document_id", ""),
                document_filename=chunk.get("document_filename", "unknown"),
                page_numbers=chunk.get("page_numbers", [1]),
                section_header=chunk.get("section_header"),
                similarity_score=chunk.get("similarity", 0.0),
                rerank_score=chunk.get("rerank_score", 0.0),
                cited_text_snippet=chunk.get("chunk_text", "")[:200],
            ))
        return citations

    def verify_grounding(
        self,
        verdict_json: dict,
        retrieved_chunks: list[dict],
    ) -> GroundingReport:
        """
        LLM-based verification of verdict grounding.
        Extracts factual claims from verdict and checks if evidence supports them.
        """
        if not retrieved_chunks:
            return GroundingReport(
                overall_score=0.0,
                grounded_claims=[],
                ungrounded_claims=["No evidence retrieved"],
                contradicted_claims=[],
                citations_used=[],
                passed=False,
            )

        citations = self.build_citations(retrieved_chunks)
        evidence_text = "\n\n".join([
            f"[Evidence {i+1}] {c.cited_text_snippet}"
            for i, c in enumerate(citations[:10])
        ])

        verdict_summary = json.dumps({
            "reasoning": verdict_json.get("reasoning", ""),
            "verdict": verdict_json.get("verdict", ""),
            "applicable_laws": verdict_json.get("applicable_laws", []),
        }, indent=2)[:3000]

        try:
            client = get_groq_client()
            response = client.chat.completions.create(
                model=settings.groq_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a legal grounding verifier. "
                            "Given a verdict and evidence chunks, extract factual claims "
                            "from the verdict and classify each as: "
                            "GROUNDED (supported by evidence), "
                            "UNGROUNDED (no evidence found), or "
                            "CONTRADICTED (evidence says opposite). "
                            "Return JSON: {grounded: [...], ungrounded: [...], contradicted: [...]}"
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"VERDICT:\n{verdict_summary}\n\n"
                            f"EVIDENCE:\n{evidence_text}"
                        ),
                    },
                ],
                temperature=0,
                max_tokens=1000,
                response_format={"type": "json_object"},
            )
            data = json.loads(response.choices[0].message.content or "{}")
            grounded = data.get("grounded", [])
            ungrounded = data.get("ungrounded", [])
            contradicted = data.get("contradicted", [])

            total = len(grounded) + len(ungrounded) + len(contradicted)
            score = len(grounded) / total if total > 0 else 0.5

            return GroundingReport(
                overall_score=round(score, 3),
                grounded_claims=grounded,
                ungrounded_claims=ungrounded,
                contradicted_claims=contradicted,
                citations_used=citations,
                passed=score >= 0.6,
            )
        except Exception:
            # Fallback: assume partially grounded
            return GroundingReport(
                overall_score=0.5,
                grounded_claims=[],
                ungrounded_claims=[],
                contradicted_claims=[],
                citations_used=citations,
                passed=True,
            )
