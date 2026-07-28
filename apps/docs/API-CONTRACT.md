# API contract (Node + Python)

Shared paths so buyers can compare runtimes.

## Auth (public)

| Method | Path | Body |
|--------|------|------|
| POST | `/api/login` | `{ "username", "password" }` |
| POST | `/api/auth/refresh` | `{ "refreshToken" }` |

## Demo (auth + `demo:read` / `demo:write`)

| Method | Path |
|--------|------|
| GET | `/api/demo/items` |
| POST | `/api/demo/items` |
| GET | `/api/demo/items/{id}` |
| PUT | `/api/demo/items/{id}` |
| DELETE | `/api/demo/items/{id}` |

Body for create: `{ "title": string, "description"?: string, "status"?: string }`

## AI (auth + `ai:chat`)

| Method | Path | Body |
|--------|------|------|
| POST | `/api/ai/chat` | `{ "message": string }` |

## Envelope

```json
{ "success": true, "data": { } }
```

```json
{ "success": false, "error": { "code": "FORBIDDEN", "message": "..." } }
```
