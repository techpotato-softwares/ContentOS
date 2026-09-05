"""ContentOS API (Python CloudArc)

```bash
cp .env.example .env   # set Supabase + keys
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
python scripts/seed.py
uvicorn src.dev_server:app --reload --port 4001
```

Modules: `platform` (auth), `tenants` (training/theme + team invites), `agent` (chat/generate), `publishing` (LinkedIn + review gate).

### Team invitations

- `POST /api/invites` · `GET /api/invites` · `DELETE /api/invites/{id}` (requires `tenant:admin`)
- `POST /api/invites/{token}/accept` (public) — creates user on the invited tenant with assigned role
- Tokens hashed at rest; statuses: pending / accepted / revoked; TTL via `TENANT_INVITE_TTL_HOURS` (default 72)
- Set `FRONTEND_URL` + `FROM_EMAIL` / `SES_FROM_EMAIL`. Local: `SES_ENABLED=false` may return `devLink`
"""
