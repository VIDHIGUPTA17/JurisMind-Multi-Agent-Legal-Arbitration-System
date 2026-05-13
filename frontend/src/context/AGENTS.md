# AGENTS.md — frontend/src/context/

## Purpose
React Context providers for global application state. Currently contains authentication state that is shared across all pages and components.

## Files

### `AuthContext.tsx`

Provides authentication state to the entire app.

**`AuthState` interface:**
```typescript
interface AuthState {
    token: string | null;
    userId: string | null;
    role: "PARTY_A" | "PARTY_B" | null;
}
```

**`AuthContext` value:**
```typescript
{
    token: string | null,
    userId: string | null,
    role: "PARTY_A" | "PARTY_B" | null,
    login: (token: string, userId: string, role: string) => void,
    logout: () => void,
}
```

**`login(token, userId, role)`:**
- Stores token in `localStorage`
- Updates context state
- Components re-render with the new auth state

**`logout()`:**
- Removes token from `localStorage`
- Clears context state (all fields → null)
- Components re-render and `ProtectedRoute` redirects to `/login`

**`useAuth()` hook:**
```typescript
import { useAuth } from "@/context/AuthContext";

const { token, userId, role, login, logout } = useAuth();
```

**`AuthProvider` setup in `App.tsx`:**
```typescript
<AuthProvider>
    <BrowserRouter>
        <Routes>...</Routes>
    </BrowserRouter>
</AuthProvider>
```

## Storage Strategy

| Data | Where stored | Why |
|---|---|---|
| JWT token | `localStorage` | Persists across browser sessions |
| userId | `localStorage` + Context | Fast access without JWT decode |
| role | `localStorage` + Context | Used to show/hide UI elements (Party A vs B) |

**Security note:** Storing JWT in `localStorage` is standard for SPAs but is vulnerable to XSS. For higher security, consider `HttpOnly` cookies — but this requires backend cookie handling.

## Role-Based UI

The `role` field controls which UI elements are shown:
- `PARTY_A`: sees "Create Case" button, not "Join Case"
- `PARTY_B`: sees "Join Case" button, not "Create Case"
- Both: see their own documents but not the other party's anonymized content
