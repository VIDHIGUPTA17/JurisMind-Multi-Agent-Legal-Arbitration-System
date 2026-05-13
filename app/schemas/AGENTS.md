# AGENTS.md — app/schemas/

## Purpose
Pydantic models for request validation and response serialization. Every API endpoint uses these for type-safe input parsing and structured output. Pydantic v2 syntax throughout.

## Files

### `auth.py`

**Request schemas:**

`RegisterRequest`
```python
email: EmailStr           # validated email format
password: str             # min length 8 chars
full_name: str            # user's full name
role: str                 # "PARTY_A" or "PARTY_B"
```

`LoginRequest`
```python
email: EmailStr
password: str
```

**Response schemas:**

`TokenResponse`
```python
access_token: str         # JWT bearer token
token_type: str           # always "bearer"
user_id: str              # UUID of created/logged-in user
role: str                 # "PARTY_A" or "PARTY_B"
```

### `case.py`

**Request schemas:**

`CaseCreateRequest`
```python
title: str
description: str | None
case_type: str            # "CONTRACT" | "CONSUMER" | "PROPERTY" | "COMPANY"
party_b_email: EmailStr   # to invite the respondent
```

`JoinCaseRequest`
```python
invite_token: str         # one-time token received from Party A
```

**Response schemas:**

`CaseResponse`
```python
id: str
title: str
description: str | None
case_type: str
status: str               # current case lifecycle status
party_a_id: str
party_b_id: str | None    # null until Party B joins
invite_token: str | None  # only shown to Party A
created_at: datetime
updated_at: datetime
```

`CaseListResponse`
```python
cases: list[CaseResponse]
total: int
```

### `document.py`

**Response schemas:**

`DocumentUploadResponse`
```python
id: str
filename: str
processing_status: str    # PENDING | PROCESSING | DONE | FAILED
task_id: str | None       # not used (kept for API compatibility)
uploaded_at: datetime
```

`DocumentResponse`
```python
id: str
case_id: str
uploader_id: str
filename: str
processing_status: str
content_anonymized: str | None  # only shown to the uploader (not opposing party)
uploaded_at: datetime
processed_at: datetime | None
```

`DocumentListResponse`
```python
documents: list[DocumentResponse]
total: int
```

### `verdict.py`

**Response schemas:**

`VerdictResponse`
```python
id: str
case_id: str
agent_a_summary: str      # JSON string of PartyAgent claimant output
agent_b_summary: str      # JSON string of PartyAgent respondent output
judge_reasoning: str      # Full reasoning from ChiefJudgeAgent
verdict_text: str         # "IN FAVOUR OF CLAIMANT" | "IN FAVOUR OF RESPONDENT" | "PARTIAL AWARD" | "DISMISSED"
applicable_laws: list[str]
relief_awarded: str
created_at: datetime
```

**Planned new fields (from CHANGES.md):**
```python
confidence_score: float | None
grounding_report: dict | None
bias_report: dict | None
settlement_recommendation: dict | None
compensation_breakdown: dict | None
```

### `arbitration.py`

Schemas for the 7-stage pipeline transparency endpoints.

**`StageResponse`**
```python
stage_number: int         # 1-7
stage_name: str           # "party_analysis", "evidence_comparison", etc.
status: str               # PENDING | RUNNING | COMPLETED | FAILED | SKIPPED
agent_name: str | None
output_summary: str | None  # human-readable summary for frontend
started_at: datetime | None
completed_at: datetime | None
duration_ms: int | None
```

**`ArbitrationProgressResponse`**
```python
case_id: str
current_stage: int
total_stages: int          # 7
stages: list[StageResponse]
```

## Validation Rules

| Field | Rule |
|---|---|
| `password` | min_length=8 |
| `email` | valid EmailStr format |
| `role` | must be "PARTY_A" or "PARTY_B" |
| `case_type` | must be one of the CaseType enum values |
| `file` | PDF only, max 20 MB (enforced in router, not schema) |

## Notes

- All schemas use `model_config = ConfigDict(from_attributes=True)` (Pydantic v2) to support ORM model → schema conversion
- Response schemas do NOT include sensitive fields like `hashed_password`, `email_hash`, `content_encrypted`
- `content_anonymized` is conditionally included: only shown when `uploader_id == current_user_id`
- Datetime fields are serialized as ISO 8601 strings by Pydantic
