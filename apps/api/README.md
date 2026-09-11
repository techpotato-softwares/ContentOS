"""ContentOS API (Python CloudArc)

```bash
cp .env.example .env   # set Supabase + keys
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
python scripts/seed.py
uvicorn src.dev_server:app --reload --port 4001
```

Modules: `platform` (auth), `tenants` (training/theme), `agent` (chat/generate), `publishing` (LinkedIn + review gate).

### Email verification & password reset (AWS SES)

- `POST /api/auth/verify-email/request` · `POST /api/auth/verify-email/confirm`
- `POST /api/auth/password-reset/request` · `POST /api/auth/password-reset/confirm`
- One-time tokens stored as SHA-256 hashes (`auth_tokens`); TTL + rate limits; no raw tokens in logs.
- `users.email_verified_at` gates LinkedIn publishing (`EMAIL_UNVERIFIED`).
- Password reset bumps `token_version` so existing JWTs fail (`SESSION_REVOKED`).
- Set `FRONTEND_URL`, `FROM_EMAIL` / `SES_FROM_EMAIL`. Production: `SES_ENABLED=true` + IAM `ses:SendEmail`.
- Local (`IS_LOCAL=true`, `SES_ENABLED=false`): emails are stubbed; responses may include `devLink` (never logged).
"""
