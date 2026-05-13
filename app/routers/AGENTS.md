# AGENTS.md — app/routers/

## Purpose
FastAPI route handlers — the HTTP API layer. Each file corresponds to a logical domain. All routes require JWT authentication (except `/auth/register` and `/auth/login`).

## Files

### `auth.py` — Prefix: `/auth`

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/register` | No | Register a new user. Returns JWT access token. |
| POST | `/auth/login` | No | Authenticate. Returns JWT access token. |

**Register flow:**
1. Hash email (SHA-256) → check uniqueness
2. Encrypt email + full_name (Fernet)
3. Hash password (bcrypt)
4. Create `User` row
5. Return JWT with `{sub: user_id, role: PARTY_A|PARTY_B}`

**Login flow:**
1. Hash email → find user by `email_hash`
2. Verify bcrypt password
3. Return JWT

**Schemas:** `RegisterRequest`, `LoginRequest`, `TokenResponse`

### `cases.py` — Prefix: `/cases`

| Method | Path | Auth | Who | Description |
|---|---|---|---|---|
| POST | `/cases` | JWT | PARTY_A only | Create a new dispute case |
| POST | `/cases/{case_id}/join` | JWT | PARTY_B only | Join case with invite token |
| GET | `/cases` | JWT | Both | List all cases where user is a party |
| GET | `/cases/{case_id}` | JWT | Both | Get case details |

**Create case:**
- Generates `invite_token` (cryptographically random, `secrets.token_urlsafe`)
- Party B must receive this token out-of-band (currently printed to console — production should email it)
- Sets `party_a_id` on the case

**Join case:**
- Validates `invite_token` matches
- Sets `party_b_id` on the case

**Schemas:** `CaseCreateRequest`, `CaseResponse`, `CaseListResponse`, `JoinCaseRequest`

### `documents.py` — Prefix: `/cases`

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/cases/{case_id}/documents` | JWT | Upload a PDF evidence document |
| GET | `/cases/{case_id}/documents` | JWT | List documents for a case |

**Upload flow:**
1. Validate: PDF only, ≤ 20 MB, case exists, user is a party, verdict not yet delivered
2. Encrypt raw PDF bytes (Fernet) and store
3. Create `Document` row with `PENDING` status
4. Auto-update case status:
   - Party A uploads → `OPEN → PARTY_A_FILED`
   - Party B uploads → `PARTY_A_FILED → PARTY_B_RESPONDED`
5. Dispatch `process_document(doc_id)` as FastAPI `BackgroundTask`

**List documents:**
- Returns metadata for all case documents
- `content_anonymized` is shown only to the document's uploader (not the opposing party)

**Schemas:** `DocumentUploadResponse`, `DocumentResponse`, `DocumentListResponse`

### `verdicts.py` — Prefix: `/cases`

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/cases/{case_id}/verdict` | JWT | Trigger AI verdict generation |
| GET | `/cases/{case_id}/verdict` | JWT | Retrieve completed verdict |

**Trigger verdict flow:**
1. Validate: case exists, user is a party, no prior verdict, both parties filed, all docs processed
2. Collect anonymized document text per party
3. Update case status → `IN_ARBITRATION`
4. **Currently:** calls `PartyAgent` + legacy `JudgeAgent` (old pipeline)
5. **Should be:** call `ArbitrationOrchestrator.run()` (new 7-stage pipeline)
6. Save `Verdict` to DB
7. Update case status → `VERDICT_DELIVERED`

**Known issue:** The router still uses the old 3-agent pipeline (PartyAgent + JudgeAgent). The `ArbitrationOrchestrator` has been built but not yet wired into this router. See CHANGES.md for the planned update.

**Debug code:** The trigger endpoint contains 100+ `print()` statements that were added for debugging. These should be replaced with `logger.info/debug()` calls before production.

**Get verdict:**
- Access-controlled: only parties A and B can read the verdict
- Returns full `VerdictResponse` with agent summaries, reasoning, laws, relief

**Schemas:** `VerdictResponse`

## Authentication Pattern

All protected routes use the `get_current_user_payload` dependency from `app.core.security`:

```python
@router.get("/cases")
async def list_cases(
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    user_id = payload["sub"]   # UUID string
    user_role = payload["role"]  # "PARTY_A" or "PARTY_B"
```

JWT is expected as `Authorization: Bearer <token>` header.

## Error Response Format

All errors use FastAPI's standard `HTTPException`:
```json
{"detail": "Error message here"}
```

Common status codes:
| Code | Meaning |
|---|---|
| 400 | Bad request (validation, wrong state) |
| 401 | Invalid or missing JWT |
| 403 | Authenticated but not authorized (wrong party) |
| 404 | Resource not found |
| 409 | Conflict (duplicate action) |
| 413 | File too large |
| 500 | AI agent or server error |

## Planned New Endpoints (from CHANGES.md)

| Method | Path | Description |
|---|---|---|
| POST | `/documents/{doc_id}/retry` | Retry a FAILED document processing |
| GET | `/cases/{id}/arbitration/stream` | SSE real-time stage updates |
| GET | `/cases/{id}/arbitration/stages` | List all pipeline stages |
| GET | `/cases/{id}/arbitration/stages/{num}` | Get specific stage details |
| POST | `/cases/{id}/arbitration/resume` | Resume from last completed stage |
| GET | `/cases/{id}/verdict/grounding` | Get grounding verification report |
| GET | `/cases/{id}/verdict/bias` | Get bias analysis report |
| POST | `/auth/refresh` | Refresh JWT access token |
