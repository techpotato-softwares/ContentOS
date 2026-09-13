# Security

## Implemented

- JWT access + refresh tokens (Secrets Manager in AWS; env locally)
- Password hashing (bcrypt)
- Bearer auth middleware on non-public routes
- `@RequirePermission` / `@RequireModule` enforcement after JWT
- Login/register rate limiting (Redis token bucket when `REDIS_URL` is set; otherwise DynamoDB `RATE_LIMIT_TABLE`, else Postgres `auth_rate_buckets`, else in-process memory). Bursts return **HTTP 429** (`RATE_LIMITED`)
- Known seed emails/passwords (`superadmin` / `demo` / `ChangeMe123!`) are rejected when `APP_ENV=production`
- Prod JWT signing keys load only from AWS Secrets Manager via `JWT_SECRET_ID` (`utils/jwt_secrets.py` + CDK `JwtSecretsConstruct`)
- No hardcoded cloud credentials or customer domains in sold defaults
- DB password fallbacks removed for non-local environments

## Auth tokens, cookies, and CORS (ops note)

- **Access JWT**: short-lived (`JWT_EXPIRES_IN`); clients send `Authorization: Bearer <accessToken>`. Prefer Bearer over cookies for this API (no CSRF on cross-site forms; SPA stores tokens in memory/local storage per product choice).
- **Refresh JWT**: longer-lived (`JWT_REFRESH_EXPIRES_IN`); exchange via `POST /api/auth/refresh` with `{ "refreshToken": "..." }`. Rotate access (and issue a new refresh) on each successful refresh; treat stolen refresh tokens as high severity — revoke by rotating Secrets Manager JWT secrets and forcing re-login.
- **Secret rotation**: change values in the Secrets Manager secret named by `JWT_SECRET_ID` (CDK: `/{app}/{env}/jwt`). Lambdas cache secrets ~5 minutes (`jwt_secrets.py`); after rotation, wait for cache expiry or redeploy. Rotating invalidates outstanding access and refresh tokens.
- **Cookies**: HttpOnly secure cookies are not used by default. If you introduce cookie sessions later, set `Secure`, `HttpOnly`, `SameSite=Strict` (or `Lax` for top-level navigations) and tighten CORS — do not combine `Access-Control-Allow-Origin: *` with credentialed cookies.
- **CORS**: API responses currently allow `*` for local/dev convenience. For production, restrict `Access-Control-Allow-Origin` to the CloudFront / custom domain origins and avoid `*` when using cookies or credentialed fetches.

## Configuration rules

- Never commit `.env` — use `.env.example` only
- Rotate any credentials that ever appeared in git history (Neon, etc.)
- Prod must set `APP_ENV=production`, `JWT_SECRET_ID`, and DB secret IDs (CDK sets these on Lambdas)
- Local/dev may keep seed users from `scripts/seed.py`; do not run seed user creation in production

## Known gaps (flagged for buyers)

| Gap | Severity | Roadmap |
|-----|----------|---------|
| No WAF in front of API Gateway | Medium | Next infra release |
| No Cognito / OAuth / MFA | Medium | Enterprise add-on |
| CORS `*` default | Medium | Restrict per env in CDK |
| Token blacklist / logout | Low | Redis-backed denylist |
| Multi-tenant RLS at DB | Medium | Postgres RLS later |
| Audit log module | Low | `audit` SKU |

## Incident note for vendors

If this repo previously contained a Neon password or customer AWS account IDs, **rotate those credentials immediately** even after scrubbing source.
