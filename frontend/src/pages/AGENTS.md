# AGENTS.md — frontend/src/pages/

## Purpose
Full-page route components. Each file corresponds to a route in `App.tsx`. Pages fetch data, manage local state, and compose smaller components.

## Files

### `Login.tsx` — Route: `/login`

**State:**
- `activeTab: "login" | "register"` — tab toggle
- `formData` — email, password, full_name, role
- `loading: boolean` — disables button during API call
- `error: string | null` — displays API error message

**Flows:**
- **Register:** `POST /auth/register` → `login(token, userId, role)` → navigate to `/cases`
- **Login:** `POST /auth/login` → `login(token, userId, role)` → navigate to `/cases`

**UI:** Gradient background, centered card with tab toggle at top.

---

### `Cases.tsx` — Route: `/cases`

**State:**
- `cases: CaseResponse[]` — list of user's cases
- `showCreateModal: boolean` — Party A create case dialog
- `showJoinModal: boolean` — Party B join case dialog
- `newCaseData` — form fields for case creation
- `inviteToken: string | null` — shown after successful case creation (copy this and give to Party B)
- `loading, error` — UI state

**API calls:**
- `GET /cases` → load cases on mount
- `POST /cases` → create case (Party A)
- `POST /cases/{id}/join` → join case (Party B)

**UI:**
- Navbar with "Logout" button
- Case cards: title, case_type, status badge, created_at, "View" link
- Role-conditional buttons:
  - Party A: "Create New Case"
  - Party B: "Join a Case"
- After create: shows invite token with copy prompt

---

### `CaseDetail.tsx` — Route: `/cases/:caseId`

**State:**
- `caseData: CaseResponse | null` — case info
- `documents: DocumentResponse[]` — all documents for this case
- `uploading: boolean` — upload in progress
- `triggeringVerdict: boolean` — AI running

**Document status polling:**
- Every 5 seconds, if any document is `PENDING` or `PROCESSING`, re-fetch document list
- Stops polling when all documents are `DONE` or `FAILED`

**API calls:**
- `GET /cases/{id}` → load case
- `GET /cases/{id}/documents` → load documents
- `POST /cases/{id}/documents` → upload PDF (multipart/form-data)
- `POST /cases/{id}/verdict` → trigger AI verdict generation

**UI sections:**
1. **Case header** — title, type, status badge, back link
2. **Upload section** — `UploadDropzone` component (disabled after verdict)
3. **Documents list** — table rows with filename, status badge, uploader label ("Your document" vs "Opposing party")
4. **Action buttons:**
   - "Trigger AI Verdict" — visible when `PARTY_B_RESPONDED` or `IN_ARBITRATION`
   - "View Verdict" — visible when `VERDICT_DELIVERED`

---

### `Verdict.tsx` — Route: `/cases/:caseId/verdict`

**State:**
- `verdict: VerdictResponse | null`
- `loading, error`

**API calls:**
- `GET /cases/{id}/verdict` → load verdict on mount

**UI:**
- Loading spinner while fetching
- `VerdictCard` component with full verdict display
- "Back to case" link

---

## Planned New Page (from CHANGES.md)

### `ArbitrationView.tsx` — Route: `/cases/:caseId/arbitration`

Real-time 7-stage pipeline progress view.

**Would replace** the simple "Trigger Verdict" button + wait → navigate flow.

**Features:**
- Progress bar: `Stage X of 7`
- 7 stage cards (Level 1 through Level 7):
  - `✅ Completed` with summary + "Expand" toggle
  - `🔄 Running...` with spinner
  - `⏳ Pending` (grayed out)
  - `❌ Failed` with error message
- Real-time updates via `EventSource` (SSE connection to `/cases/{id}/arbitration/stream`)
- Expandable stage cards showing:
  - Agreed facts vs disputed facts
  - Evidence citations (document + page)
  - Legal issues with statute references
  - Compensation breakdown
  - Contradiction details

**SSE event handling:**
```typescript
const es = new EventSource(`/api/cases/${id}/arbitration/stream`);
es.addEventListener("stage_completed", (e) => {
    const data = JSON.parse(e.data);
    setStages(prev => updateStage(prev, data));
});
es.addEventListener("verdict_ready", (e) => {
    navigate(`/cases/${id}/verdict`);
});
```
