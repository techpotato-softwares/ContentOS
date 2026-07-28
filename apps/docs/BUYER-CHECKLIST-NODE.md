# Buyer checklist — ArcForge Node

1. [ ] Purchase license / receive private access
2. [ ] Clone or unzip the Node tree (`api/` + `cdk/` + `docs/`)
3. [ ] Copy `api/.env.example` → `api/.env` and set secrets
4. [ ] `docker compose up -d` (Postgres)
5. [ ] `cd api && npm install && npm run db:generate && npm run db:push`
6. [ ] Seed admin (`npm run db:seed:admin`) — set `ADMIN_EMAIL` / `ADMIN_PASSWORD`
7. [ ] `npm run build:all && npm run dev:express`
8. [ ] Login via `POST /api/login`; exercise `/api/demo/items`
9. [ ] Configure CDK env hosts/secrets for your AWS account (no sample account IDs)
10. [ ] Deploy `ApiStack-dev`; smoke-test API Gateway URL
11. [ ] Restrict CORS and set production JWT secrets in Secrets Manager
12. [ ] Read [SECURITY.md](SECURITY.md) gap flags before go-live
