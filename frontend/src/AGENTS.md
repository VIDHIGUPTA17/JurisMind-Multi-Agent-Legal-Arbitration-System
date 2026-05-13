# AGENTS.md — frontend/src/

## Purpose
Source root of the React application. Contains the app entry point, router setup, and all feature sub-directories.

## Files

### `main.tsx`
React application entry point. Mounts `<App />` into `#root` DOM element with `StrictMode`.

### `App.tsx`
React Router v6 setup. Defines all routes and wraps them with `AuthProvider`.

**Routes:**
```
/login                        → Login.tsx (public)
/cases                        → Cases.tsx (protected)
/cases/:caseId                → CaseDetail.tsx (protected)
/cases/:caseId/verdict        → Verdict.tsx (protected)
*                             → redirect to /cases
```

**`ProtectedRoute`** component:
- Reads token from `useAuth()`
- If no token → redirect to `/login`
- If token exists → render children

### `index.css`
Global CSS file. Imports Tailwind CSS directives:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```
Custom base styles (font, background color) may also be here.

## Sub-directories

| Directory | Description |
|---|---|
| `api/` | Axios HTTP client configuration |
| `context/` | React Context providers (auth state) |
| `pages/` | Full-page route components |
| `components/` | Reusable UI components |

## Data Flow

```
User action (click/form submit)
    │
    ▼
Page component (pages/*.tsx)
    │
    ▼
api/client.ts (Axios call with JWT)
    │
    ▼
FastAPI Backend (localhost:8000)
    │
    ▼
JSON response
    │
    ▼
Component state update → re-render
```
