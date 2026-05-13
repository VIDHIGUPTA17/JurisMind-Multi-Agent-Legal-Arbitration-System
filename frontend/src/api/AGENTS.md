# AGENTS.md — frontend/src/api/

## Purpose
HTTP client configuration. Single Axios instance shared by all components — handles base URL, JWT injection, and automatic logout on 401.

## Files

### `client.ts`

**Axios instance:**
```typescript
const client = axios.create({
    baseURL: "/api",           // proxied by Vite to http://localhost:8000
    timeout: 30000,            // 30 second timeout (important for long AI calls)
});
```

**Request interceptor** — attaches JWT Bearer token to every outgoing request:
```typescript
client.interceptors.request.use((config) => {
    const token = localStorage.getItem("token");
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});
```

**Response interceptor** — handles auth errors globally:
```typescript
client.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            localStorage.removeItem("token");
            window.location.href = "/login";
        }
        return Promise.reject(error);
    }
);
```

**Why a single Axios instance:**
- Avoids duplicating auth headers in every component
- Centralizes error handling
- Easy to add global request/response logging

**Usage in components:**
```typescript
import client from "@/api/client";

// GET request
const { data } = await client.get(`/cases/${caseId}`);

// POST request
const { data } = await client.post("/auth/login", { email, password });

// File upload (FormData)
const formData = new FormData();
formData.append("file", pdfFile);
await client.post(`/cases/${caseId}/documents`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
});
```

## Notes

- Token is stored in `localStorage` (not `sessionStorage`) — persists across browser tabs and page refreshes
- The 401 interceptor performs a hard redirect (`window.location.href`) rather than using React Router — this ensures all in-flight requests are cancelled
- For the planned SSE streaming (from CHANGES.md), use the native `EventSource` API directly (not Axios), since SSE is not a standard HTTP request/response:
  ```typescript
  const es = new EventSource(`/api/cases/${caseId}/arbitration/stream`, {
      headers: { Authorization: `Bearer ${token}` },
  });
  ```
