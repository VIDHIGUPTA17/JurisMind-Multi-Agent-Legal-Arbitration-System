# AGENTS.md — app/agents/

## Purpose
Contains all AI agents that power the multi-agent arbitration pipeline. Each agent is a specialist with a single responsibility. The `orchestrator.py` coordinates them across 7 sequential stages.

## Files

### `base_agent.py`
Foundation class for every agent. Provides:
- Singleton Groq client (`get_groq_client()`)
- `_chat(messages, json_mode, tools)` — calls Groq API with exponential-backoff retry (up to 2 retries)
- Returns `(response_text: str, tokens_used: int)` tuple
- `_parse_json(text, fallback)` — safely parses LLM JSON output, searches for JSON object if response has extra text
- All agents inherit from `BaseAgent` and set `name`, `temperature`, `max_tokens`

### `orchestrator.py`
Controls the 7-stage pipeline end-to-end. Key responsibilities:
- Runs stages sequentially; runs agents within a stage in parallel (`asyncio.gather`)
- After each stage: writes `ArbitrationStage` record to DB, broadcasts SSE event
- Manages `_sse_queues` (in-memory `asyncio.Queue` per case for real-time updates)
- Exports `subscribe_to_case(case_id)` and `unsubscribe_from_case(case_id, q)` for SSE router
- Returns full pipeline result dict including final verdict, grounding report, compensation

**Pipeline stages:**
```
Stage 1  party_analysis          PartyAgent × 2 (parallel)
Stage 2  evidence_comparison     EvidenceComparisonAgent
Stage 3  contradiction_check     ContradictionDetectionAgent + WitnessConsistencyAgent (parallel)
Stage 4  legal_reasoning         LegalArgumentAgent → LiabilityReasoningAgent (sequential)
Stage 5  resolution              CompensationCalculationAgent + SettlementRecommendationAgent (parallel)
Stage 6  quality_assurance       BiasConflictAgent
Stage 7  final_verdict           ChiefJudgeAgent + CitationTracker grounding verification
```

### `party_agent.py`
Represents one party (CLAIMANT or RESPONDENT). Called twice in Stage 1.
- `summarise(role, documents_text) → dict`
- Output: `{claims/defences[], key_facts[], relief_sought, applicable_laws_suggested[], overall_strength_assessment, documents_summary}`
- Each claim MUST include `evidence_basis` (cited from docs) and `strength` (STRONG/MODERATE/WEAK)
- Truncates input to 12,000 chars to stay within token limits

### `evidence_comparison_agent.py`
Stage 2 — Cross-references party claims against actual RAG evidence chunks.
- `compare(claimant_summary, respondent_summary, evidence_chunks) → dict`
- For each claim: marks `SUPPORTED`, `NOT_FOUND`, or `CONTRADICTED` with evidence reference
- Output counts: `supported_count`, `not_found_count`, `contradicted_count`

### `contradiction_detection_agent.py`
Stage 3 — Finds contradictions and agreements between the two parties.
- `detect(claimant_summary, respondent_summary, evidence_map) → dict`
- Output: `agreed_facts[]`, `disputed_facts[]` (each with claimant/respondent position + evidence support + dispute type), `unilateral_claims[]`
- Categorizes disputes as `FACTUAL | LEGAL | MIXED`

### `witness_consistency_agent.py`
Stage 3 — Checks internal consistency of each party's own documents.
- `check_consistency(party, documents_text) → dict`
- Looks for: date inconsistencies, amount discrepancies, timeline gaps, contradictory statements within same party's docs
- Output: `internal_contradictions[]`, `timeline_issues[]`, `consistency_score` (0.0–1.0), `credibility_impact`

### `legal_argument_agent.py`
Stage 4 — Maps disputed facts to specific Indian statutes and constructs arguments for both sides.
- `generate_arguments(contradiction_report, evidence_map, claimant_summary, respondent_summary) → dict`
- Applies: ICA 1872, Arbitration Act 1996, Specific Relief Act 1963, TPA 1882, CPA 2019, Companies Act 2013
- Output: `legal_issues[]` each with `claimant_argument`, `respondent_argument`, `applicable_law`, `burden_of_proof`, `evidence_weight`

### `liability_reasoning_agent.py`
Stage 4 — Determines which party bears liability and to what degree.
- `determine_liability(legal_analysis, contradiction_report) → dict`
- Applies: reasonable person test, but-for causation, proximate cause, contributory negligence
- Output: `primary_liability`, `liability_split {claimant_percent, respondent_percent}`, `breach_type`, `reasoning_per_issue[]`

### `compensation_calculation_agent.py`
Stage 5 — Calculates structured damages award in INR.
- `calculate(liability_determination, evidence_chunks, claimant_summary) → dict`
- Framework: compensatory damages (Section 73 ICA 1872), consequential damages, interest (RBI rates), deductions, litigation costs
- Output: `compensatory_damages`, `consequential_damages`, `interest_rate_percent`, `interest_amount`, `deductions{}`, `total_award`, `calculation_methodology`
- Only awards damages proved by evidence (not speculative)

### `settlement_recommendation_agent.py`
Stage 5 — Assesses if mediated settlement would be better than full arbitration.
- `recommend(liability_determination, compensation_breakdown) → dict`
- Output: `settlement_recommended` (bool), `recommended_settlement_range {min, max}`, `rationale`, `compromise_points[]`, `benefits_of_settlement[]`

### `bias_conflict_agent.py`
Stage 6 — Reviews entire pipeline for bias or unfairness.
- `analyze(pipeline_context) → dict`
- Checks: evidence imbalance, ignored arguments, compensation reasonableness, circular reasoning
- Output: `overall_bias_score` (0.0–1.0), `bias_level`, `evidence_balance{}`, `flags[]`, `passed` (bool)

### `chief_judge_agent.py`
Stage 7 — Synthesizes all specialist agent outputs into the final binding arbitration award.
- `deliberate(pipeline_context) → dict`
- Output: `verdict` (IN FAVOUR OF CLAIMANT/RESPONDENT/PARTIAL AWARD/DISMISSED), `applicable_laws[]`, `key_issues_determined[]`, `reasoning`, `relief_awarded{}`, `confidence_score`, `bias_attestation`

### `judge_agent.py`
**Legacy** — original single-pass judge using Groq tool-use API. Kept for backward compatibility. Replaced by `chief_judge_agent.py` in the new pipeline.

## Data Flow

```
claimant_docs ──► PartyAgent ──────────────────────────────────────────────────►
                                                                                  ├──► EvidenceComparisonAgent
respondent_docs ► PartyAgent ──────────────────────────────────────────────────►
                                    │
                              evidence_chunks (from RAG retriever)
                                    │
                              ContradictionDetectionAgent ──►
                              WitnessConsistencyAgent      ──►  LegalArgumentAgent
                                                                      │
                                                               LiabilityReasoningAgent
                                                                      │
                                                          CompensationCalculationAgent
                                                          SettlementRecommendationAgent
                                                                      │
                                                               BiasConflictAgent
                                                                      │
                                                              ChiefJudgeAgent
                                                                      │
                                                              FinalVerdict + GroundingReport
```

## Groq API Budget per Verdict

| Stage | Agents | Calls |
|---|---|---|
| 1 | PartyAgent × 2 | 2 |
| 2 | EvidenceComparisonAgent | 1 |
| 3 | ContradictionDetectionAgent + WitnessConsistencyAgent × 2 | 3 |
| 4 | LegalArgumentAgent + LiabilityReasoningAgent | 2 |
| 5 | CompensationCalculationAgent + SettlementRecommendationAgent | 2 |
| 6 | BiasConflictAgent | 1 |
| 7 | ChiefJudgeAgent + GroundingVerification | 2 |
| **Total** | | **~13–17 calls** |

## Important Notes

- All agents are **synchronous** (Groq Python SDK is sync). The orchestrator runs them via `asyncio.get_running_loop().run_in_executor(None, ...)` to avoid blocking the async event loop.
- Each agent pops `_tokens_used` from its return dict — the orchestrator accumulates total token count.
- `temperature=0.2` by default (low randomness for deterministic legal reasoning).
- Model: `llama-3.3-70b-versatile` via Groq API (configured in `app/config.py`).
