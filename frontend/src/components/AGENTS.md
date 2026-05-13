# AGENTS.md — frontend/src/components/

## Purpose
Reusable UI components shared across multiple pages. Each component is focused on a single visual concern and accepts props to customize its display.

## Files

### `StatusBadge.tsx`

Colored pill badge for displaying status values.

**Props:**
```typescript
interface StatusBadgeProps {
    status: string;
    size?: "normal" | "small";
}
```

**Case status colors:**
| Status | Color |
|---|---|
| `OPEN` | Gray |
| `PARTY_A_FILED` | Blue |
| `PARTY_B_RESPONDED` | Purple |
| `IN_ARBITRATION` | Yellow/Orange |
| `VERDICT_DELIVERED` | Green |

**Document processing status colors:**
| Status | Color |
|---|---|
| `PENDING` | Gray |
| `PROCESSING` | Blue (animated?) |
| `DONE` | Green |
| `FAILED` | Red |

**Usage:**
```tsx
<StatusBadge status={case.status} />
<StatusBadge status={doc.processing_status} size="small" />
```

---

### `UploadDropzone.tsx`

PDF drag-and-drop file upload zone powered by `react-dropzone`.

**Props:**
```typescript
interface UploadDropzoneProps {
    onUpload: (file: File) => Promise<void>;
    disabled?: boolean;
    loading?: boolean;
}
```

**Behavior:**
- Accepts: PDF files only (`accept={{ "application/pdf": [".pdf"] }}`)
- Max files: 1 at a time
- Drag-active: visual border/background change
- `disabled=true`: grays out, no interaction (used after verdict delivered)
- `loading=true`: shows spinner, prevents re-upload during in-progress upload

**Visual states:**
1. Default: dashed border, "Drag & drop PDF here, or click to select"
2. Drag-active: solid highlight border
3. Loading: spinner overlay
4. Disabled: muted colors, cursor not-allowed

**Usage in `CaseDetail.tsx`:**
```tsx
<UploadDropzone
    onUpload={handleUpload}
    disabled={case.status === "VERDICT_DELIVERED"}
    loading={uploading}
/>
```

---

### `VerdictCard.tsx`

Structured display of the final arbitration verdict.

**Props:**
```typescript
interface VerdictCardProps {
    verdict: VerdictResponse;
}
```

**Display sections:**

1. **Verdict Banner** — large colored header
   - `IN FAVOUR OF CLAIMANT` → green
   - `IN FAVOUR OF RESPONDENT` → red
   - `PARTIAL AWARD` → yellow
   - `DISMISSED` → gray

2. **Applicable Laws** — bullet list of law references
   ```
   • Indian Contract Act 1872, Section 73
   • Arbitration and Conciliation Act 1996
   ```

3. **Judge's Reasoning** — `whitespace-pre-wrap` formatted text block (preserves line breaks from the LLM output)

4. **Claimant Position** (parsed from `agent_a_summary` JSON string)
   - Claims list
   - Relief sought
   - Strength assessment badge

5. **Respondent Position** (parsed from `agent_b_summary` JSON string)
   - Defences list
   - Strength assessment badge

**JSON parsing:**
```typescript
const claimantData = JSON.parse(verdict.agent_a_summary || "{}");
const respondentData = JSON.parse(verdict.agent_b_summary || "{}");
```
Falls back to empty object `{}` if parsing fails.

---

## Planned New Components (from CHANGES.md)

### `StageCard.tsx`
Expandable card for one pipeline stage in `ArbitrationView`.

**Props:** `{ stage: StageResponse, expanded: boolean, onToggle: () => void }`

**Collapsed:** Shows stage name, status icon, duration, one-line summary.

**Expanded:** Shows full stage output — agreed facts, disputed facts, legal issues, citations.

### `CitationViewer.tsx`
Displays document citations with source attribution.

**Shows:** Document filename, page number, section header, text snippet, similarity score.

### `ContradictionMap.tsx`
Visual representation of contradictions between parties.

**Shows:** Each disputed fact with claimant/respondent positions side-by-side, evidence support indicator, dispute type badge.
