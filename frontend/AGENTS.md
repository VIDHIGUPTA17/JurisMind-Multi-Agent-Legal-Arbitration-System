# AGENTS.md — frontend/

## Purpose
React 18 + TypeScript + Vite frontend for the AI Legal Arbitration System. Communicates with the FastAPI backend via REST API. Built with Tailwind CSS for styling.

## Directory Structure

```
frontend/
├── src/
│   ├── api/
│   │   └── client.ts          # Axios HTTP client with JWT interceptor
│   ├── context/
│   │   └── AuthContext.tsx    # Global auth state (token, userId, role)
│   ├── pages/
│   │   ├── Login.tsx          # Login / Register page
│   │   ├── Cases.tsx          # Case list + create/join modals
│   │   ├── CaseDetail.tsx     # Case detail, document upload, verdict trigger
│   │   └── Verdict.tsx        # Verdict display page
│   ├── components/
│   │   ├── StatusBadge.tsx    # Colored status indicator
│   │   ├── UploadDropzone.tsx # PDF drag-and-drop upload zone
│   │   └── VerdictCard.tsx    # Verdict structured display
│   ├── App.tsx                # React Router setup + protected routes
│   ├── main.tsx               # React app entry point
│   └── index.css              # Global Tailwind CSS
├── index.html                 # HTML entry point
├── package.json               # Node dependencies
├── vite.config.ts             # Vite config (proxy to :8000)
├── tsconfig.json              # TypeScript config
└── tailwind.config.js         # Tailwind config
```

## How to Run

```bash
cd frontend
npm install
npm run dev     # starts on http://localhost:5173
```

The Vite dev server proxies `/api/*` requests to `http://localhost:8000` — so the frontend calls `/api/auth/login` and Vite forwards it to the FastAPI server.

## Tech Stack

| Library | Version | Purpose |
|---|---|---|
| React | 18 | UI framework |
| TypeScript | 5 | Type safety |
| Vite | 5 | Build tool + dev server |
| Tailwind CSS | 3 | Utility-first CSS |
| React Router | 6 | Client-side routing |
| Axios | 1 | HTTP client |
| react-dropzone | — | PDF drag-drop upload |

## Key Pages

### `/login` — Login.tsx
- Tab toggle: Sign In / Register
- Register: email, password, full_name, role (PARTY_A / PARTY_B)
- Login: email, password
- On success: stores JWT in `AuthContext`, navigates to `/cases`

### `/cases` — Cases.tsx
- Lists all cases where current user is a party
- PARTY_A: "Create New Case" modal (title, description, case_type, party_b_email)
- PARTY_B: "Join Case" modal (case_id + invite_token)
- Shows invite token after case creation (copy-paste to give to Party B)

### `/cases/:caseId` — CaseDetail.tsx
- Case info header (title, type, status badge)
- Document upload section (drag-drop, PDF only)
- Document list with processing status (polls every 5 seconds while PENDING)
- "Trigger AI Verdict" button (visible when status = PARTY_B_RESPONDED or IN_ARBITRATION)
- "View Verdict" button (visible when VERDICT_DELIVERED)
- Disables upload after verdict delivered

### `/cases/:caseId/verdict` — Verdict.tsx
- Fetches verdict from `GET /cases/{id}/verdict`
- Renders `VerdictCard` component
- Loading spinner while fetching

## Authentication Flow

1. `AuthContext` wraps the entire app (in `main.tsx`)
2. JWT stored in `localStorage` key `"token"`
3. `useAuth()` hook provides `{ token, userId, role, login, logout }`
4. `ProtectedRoute` in `App.tsx` redirects to `/login` if no token
5. Axios interceptor attaches `Authorization: Bearer {token}` to every request
6. Axios 401 response interceptor calls `logout()` and redirects to `/login`

## API Communication

All API calls go through `src/api/client.ts`:
```typescript
const client = axios.create({ baseURL: "/api" });
// Request interceptor: adds Bearer token
// Response interceptor: handles 401 → logout
```

Example call:
```typescript
const response = await client.post("/auth/login", { email, password });
const { access_token, user_id, role } = response.data;
```

## Planned New Components (from CHANGES.md)

| Component | Purpose |
|---|---|
| `pages/ArbitrationView.tsx` | 7-level transparent pipeline progress view |
| `components/StageCard.tsx` | Expandable card for each pipeline stage |
| `hooks/useArbitrationStream.ts` | SSE connection for real-time stage updates |
| `components/CitationViewer.tsx` | Show evidence citations per claim |
| `components/ContradictionMap.tsx` | Visual contradiction map between parties |

The `ArbitrationView` would replace the simple "Trigger Verdict" button with a real-time progress view showing each of the 7 stages as they complete, with expandable detail cards showing evidence, contradictions, legal analysis, and compensation.
