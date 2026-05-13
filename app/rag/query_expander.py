"""
Query expansion for legal queries.
Expands a single query into multiple search angles to improve recall.
"""
from __future__ import annotations
import json
from app.agents.base_agent import get_groq_client
from app.config import get_settings
settings = get_settings()

# Legal synonym expansions (static, no LLM call needed)
_LEGAL_SYNONYMS: dict[str, list[str]] = {
    "breach": ["violation", "non-compliance", "failure to perform", "default"],
    "contract": ["agreement", "deed", "instrument", "undertaking"],
    "damages": ["compensation", "relief", "award", "remedy", "indemnity"],
    "termination": ["cancellation", "rescission", "dissolution", "repudiation"],
    "payment": ["consideration", "remuneration", "amount due", "outstanding dues"],
    "property": ["immovable property", "asset", "real estate", "premises"],
    "negligence": ["carelessness", "breach of duty", "failure to take care"],
    "fraud": ["misrepresentation", "deceit", "wilful default", "dishonesty"],
    "deliver": ["supply", "provide", "furnish", "hand over"],
    "force majeure": ["act of god", "natural disaster", "unforeseen circumstances"],
}

_STATUTE_MAP: dict[str, str] = {
    "breach of contract": "Section 73 Indian Contract Act 1872",
    "specific performance": "Specific Relief Act 1963",
    "fraud": "Section 17 Indian Contract Act 1872",
    "negligence": "Law of Torts",
    "arbitration": "Arbitration and Conciliation Act 1996",
    "consumer": "Consumer Protection Act 2019",
    "property": "Transfer of Property Act 1882",
    "company": "Companies Act 2013",
}


class QueryExpander:
    """
    Expand a single legal query into multiple search angles.
    Uses static synonym map + optional LLM expansion.
    """

    def expand(self, query: str, use_llm: bool = False) -> list[str]:
        """
        Returns list of expanded queries (deduped, original first).
        """
        queries = [query]

        # Static synonym expansion
        query_lower = query.lower()
        for term, synonyms in _LEGAL_SYNONYMS.items():
            if term in query_lower:
                for syn in synonyms[:2]:  # max 2 synonyms per term
                    expanded = query_lower.replace(term, syn)
                    if expanded not in queries:
                        queries.append(expanded)

        # Statute reference expansion
        for key, statute in _STATUTE_MAP.items():
            if key in query_lower and statute not in " ".join(queries):
                queries.append(f"{query} {statute}")
                break  # only add one statute reference

        # LLM expansion (optional, costs one Groq call)
        if use_llm and len(queries) < 3:
            try:
                llm_queries = self._llm_expand(query)
                for q in llm_queries:
                    if q not in queries:
                        queries.append(q)
            except Exception:
                pass  # fallback gracefully

        return queries[:5]  # cap at 5 total

    def _llm_expand(self, query: str) -> list[str]:
        client = get_groq_client()
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a legal search query expander. "
                        "Given a legal query, return 2-3 alternative phrasings "
                        "using different legal terminology. "
                        "Return ONLY a JSON array of strings, no explanation."
                    ),
                },
                {"role": "user", "content": f"Query: {query}"},
            ],
            temperature=0,
            max_tokens=200,
            response_format={"type": "json_object"},
        )
        text = response.choices[0].message.content or "[]"
        data = json.loads(text)
        if isinstance(data, list):
            return [str(q) for q in data]
        # Handle {"queries": [...]} format
        for v in data.values():
            if isinstance(v, list):
                return [str(q) for q in v]
        return []
