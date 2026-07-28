# Security

## Implemented

- JWT access + refresh tokens (Secrets Manager in AWS; env locally)
- Password hashing (bcrypt)
- Bearer auth middleware on non-public routes
- `@RequirePermission` / `@RequireModule` enforcement after JWT
- User registration is **not** public (requires permission)
- No hardcoded cloud credentials or customer domains in sold defaults
- DB password fallbacks removed for non-local environments

## Configuration rules

- Never commit `.env` — use `.env.example` only
- Rotate any credentials that ever appeared in git history (Neon, etc.)
- Prod must set `JWT_SECRET_ID` / DB secret IDs

## Known gaps (flagged for buyers)

| Gap | Severity | Roadmap |
|-----|----------|---------|
| No WAF / rate limiting | Medium | Next infra release |
| No Cognito / OAuth / MFA | Medium | Enterprise add-on |
| CORS `*` default | Medium | Restrict per env in CDK |
| Token blacklist / logout | Low | Redis-backed denylist |
| Multi-tenant RLS at DB | Medium | Postgres RLS later |
| Audit log module | Low | `audit` SKU |

## Incident note for vendors

If this repo previously contained a Neon password or customer AWS account IDs, **rotate those credentials immediately** even after scrubbing source.
