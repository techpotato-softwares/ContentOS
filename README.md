# ContentOS

**ContentOS** is a B2B, multi-tenant **LinkedIn content operating system**. Teams train the product on their company (brand, domain, offerings, voice), then use an AI agent to generate on-brand **image + caption** LinkedIn posts, review them manually, and publish — with insights for what to post and placeholder analytics for when to post.

The goal: automate LinkedIn content creation so companies spend less time researching and designing, and more time publishing consistently for reach and followers.

---

## What it does

| Area | Capability |
|------|------------|
| **Company training** | Structured brand/domain schema (colors, voice, offerings, contact) injected into generation |
| **Agent chat** | Open briefs → conversation + variants (**text**, **image**, or **carousel**) |
| **Chat history** | Persisted sessions you can reopen; PDF/URL attach as draft then Send with context |
| **Insights** | Domain content suggestions + industry briefings as generation context |
| **Analytics** | Placeholder LinkedIn metrics + AI tips on what/when to publish |
| **Review & publish** | Manual approve/reject gate, then LinkedIn publish (personal or company page) |
| **Multi-tenant** | Platform theme by default; white-label when tenant logo + colors are complete |
| **Roles** | `super_admin` · `tenant_admin` · `tenant_member` |

Typical flow:

```text
Training → Insights (optional) → Agent generate → Review → LinkedIn publish
```

---

## Repository layout

```text
ContentOS/
├── apps/
│   ├── api/                 # Python API (CloudArc-style modules → local FastAPI / AWS Lambda)
│   │   ├── modules/         # platform (auth), tenants, agent, publishing
│   │   ├── layers/shared/   # shared DB models, training schema, middleware
│   │   ├── src/dev_server.py
│   │   ├── scripts/seed.py
│   │   ├── media/           # local generated images (gitignored)
│   │   └── .env.example
│   ├── web/                 # React + Vite SPA (Redux Toolkit, RTK Query, Tailwind, Framer Motion, Three.js)
│   └── docs/                # Framework / platform docs (architecture, security, etc.)
├── infra/                   # AWS CDK (Python) — API Lambdas, secrets, S3, optional static hosting
├── Docs/ / RequirementDocs/ # Product PRD / TRD / PRR (Word)
├── package.json             # Root scripts for API, web, DB, deploy
└── README.md                # ← you are here
```

| Path | Stack |
|------|--------|
| `apps/api` | Python 3.9+, FastAPI/Uvicorn locally, SQLModel, Postgres, JWT, OpenAI (or Bedrock/stub) |
| `apps/web` | React 19, TypeScript, Vite, Redux Toolkit + RTK Query, Tailwind v4, shadcn-style UI |
| `infra` | AWS CDK — Lambdas: auth, tenants, agent, publishing |

---

## Prerequisites

| Tool | Version / notes |
|------|-----------------|
| **Node.js** | ≥ 20 |
| **Python** | ≥ 3.9 (`python3`) |
| **Postgres** | Supabase project (local & QA). Set `DB_SSL=true`. Prod uses RDS via CDK. |
| **OpenAI API key** | Required for real chat + image generation (`AI_PROVIDER=openai`) |
| **LinkedIn app** (optional) | Client ID/secret for live connect & publish. Member posting needs Share on LinkedIn + OpenID. **Company pages** need Community Management API (`w_organization_social`, `r_organization_admin`). |

---

## Onboarding a new team member

Follow this checklist once after cloning.

### 1. Clone & install

```bash
git clone <repo-url>
cd ContentOS

# API virtualenv + dependencies
npm run install:api

# Web dependencies
npm run install:web
```

### 2. Configure environment

```bash
cp apps/api/.env.example apps/api/.env
```

Edit `apps/api/.env` with at least:

| Variable | Purpose |
|----------|---------|
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USERNAME`, `DB_PASSWORD` | Supabase Postgres (preferred over raw `DATABASE_URL` if password has `@` etc.) |
| `DB_SSL=true` | Required for Supabase |
| `JWT_SECRET` / `JWT_REFRESH_SECRET` | ≥ 32 chars each |
| `AI_PROVIDER=openai` | Or `stub` / `bedrock` |
| `OPENAI_API_KEY` | From OpenAI dashboard |
| `OPENAI_IMAGE_MODEL=gpt-image-1` | Image model your org can access |
| `OPENAI_IMAGE_SIZE=1536x1024` | Landscape LinkedIn-friendly size |
| `PUBLIC_API_URL=http://localhost:4001` | Local media URLs |
| `IS_LOCAL=true` | Local media files under `apps/api/media/` |

Ask a teammate for shared **Supabase** credentials and a **dev OpenAI** key (or create your own). **Never commit** `apps/api/.env`.

Optional later:

- `LINKEDIN_CLIENT_ID` / `LINKEDIN_CLIENT_SECRET` for publishing
- Infra: `npm run install:infra` and `infra/env.template.json` → `env.local.json` (gitignored)

### 3. Initialize the database

```bash
npm run db:init
```

Creates tables and seeds roles, permissions, and demo users.

### 4. Run API + UI (two terminals)

```bash
# Terminal 1 — API :4001
npm run dev:api

# Terminal 2 — Web :5173
npm run dev:web
```

Open **http://localhost:5173** and sign in.

### 5. Seed logins

| Username | Password | Role |
|----------|----------|------|
| `superadmin` | `ChangeMe123!` | Platform super admin (all tenants) |
| `demo` | `ChangeMe123!` | Tenant admin for **Demo Co** |

Change these passwords before any shared or production use.

### 6. First product walkthrough

1. **Training** — fill company industry/domain, brand colors, website/phone/email  
2. **Insights** — suggestions & industry briefings → “Generate from this”  
3. **Agent** — choose format (text / image / carousel); attach PDF or URL as a draft chip, add context, then Send; or Generate for briefs  
4. **Review** — approve drafts; pick personal vs company page when both are connected  
5. **LinkedIn** — connect personal profile and/or company page (admin), then publish  
6. **Analytics** — placeholder metrics + AI publish guidance  

### LinkedIn OAuth setup

1. Create an app at [LinkedIn Developers](https://www.linkedin.com/developers/).
2. Enable **Sign In with LinkedIn using OpenID Connect** and **Share on LinkedIn** (member posts).
3. For company pages: apply for **Community Management API**, then use scopes including `w_organization_social` and `r_organization_admin`.
4. Authorized redirect URL must match `LINKEDIN_REDIRECT_URI` (default `http://localhost:4001/api/social/linkedin/callback`).
5. Set `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`, `LINKEDIN_REDIRECT_URI`, `LINKEDIN_FRONTEND_REDIRECT` in `apps/api/.env`.
6. In the app: **LinkedIn** → Connect personal (any publisher) and/or Connect company page (tenant admin) → pick the page after OAuth.

**Post formats:** text captions publish via UGC; carousels are composed as multi-slide images and published as a LinkedIn document when document APIs are available.

### 7. Read next (optional)

| Doc | Where |
|-----|--------|
| Product / TRD | `Docs/` or `RequirementDocs/` |
| API contract / architecture | `apps/docs/` |
| Infra deploy | `infra/README.md` |

---

## Day-to-day: start servers

From the **repo root**:

```bash
# API (reload enabled)
npm run dev:api
# → http://localhost:4001
# → health: http://localhost:4001/health
# → OpenAPI-ish via FastAPI; media: http://localhost:4001/media/...

# UI
npm run dev:web
# → http://localhost:5173
# Vite proxies /api, /health, and /media → :4001
```

Stop with `Ctrl+C` in each terminal. After changing `apps/api/.env`, restart `dev:api` so env vars reload.

---

## Useful npm scripts (root)

| Script | Description |
|--------|-------------|
| `npm run install:api` | Create `apps/api/.venv` and install Python package |
| `npm run install:web` | `npm install` in `apps/web` |
| `npm run install:infra` | CDK Python venv |
| `npm run db:init` | Create/migrate seed data |
| `npm run dev:api` | Uvicorn on port **4001** |
| `npm run dev:web` | Vite on port **5173** |
| `npm run build:web` | Production web build |
| `npm run build:layer` | Build Lambda dependency layer |
| `npm run test` | API pytest |
| `npm run synth:dev` / `deploy:dev` / `deploy:qa` | CDK synth/deploy |

---

## Environments

| Environment | Database | Notes |
|-------------|----------|--------|
| **Local** | Supabase Postgres + SSL | Images → `apps/api/media/` |
| **QA** | Same Supabase pattern | Deploy via CDK |
| **Prod** | RDS / Aurora (CDK) | S3 for assets; secrets in AWS |

---

## API modules (high level)

| Module | Responsibility |
|--------|----------------|
| `platform` | Register, login, JWT refresh, `/api/me` |
| `tenants` | Tenant CRUD (admin), theme, training schema/docs |
| `agent` | Chat sessions/history, generate 3 variants, insights (suggestions/news/analytics) |
| `publishing` | LinkedIn OAuth, posts list, submit/approve/reject/publish |

Local images are served at `/media/...`. In production, uploads go to S3.

---

## Web app routes

| Route | Page |
|-------|------|
| `/login` | Auth |
| `/dashboard` | Overview + recent creatives |
| `/agent` | Chat, history, generate |
| `/insights` | Suggestions & industry news |
| `/analytics` | Analytics placeholder + AI advice |
| `/review` | Review & publish queue |
| `/connections/linkedin` | LinkedIn connect |
| `/settings/training` | Company training |
| `/admin/tenants` | Super-admin tenants |

---

## AI configuration notes

- Prefer `OPENAI_IMAGE_SIZE=1536x1024` for landscape LinkedIn graphics.  
- If image calls fail with model/quota errors, check OpenAI billing and that `OPENAI_IMAGE_MODEL` exists on your account.  
- `AI_PROVIDER=stub` runs without OpenAI (placeholder images) for UI-only work.  
- Long story copy belongs in the **caption**; on-image text is kept short to avoid cut-off letters.

---

## Deploy (summary)

```bash
npm run build:layer
npm run build:web
npm run install:infra
cd infra && source .venv/bin/activate
# Configure env from env.template.json → secrets / env.local.json
cdk synth ApiStack-dev   # or use npm run synth:dev / deploy:qa
```

See [`infra/README.md`](infra/README.md) for Lambda names and DB wiring.

---

## Troubleshooting

| Problem | What to try |
|---------|-------------|
| `python: command not found` | Root scripts use `apps/api/.venv/bin/python` — run `npm run install:api` first |
| DB auth fails / password has `@` | Use `DB_*` fields; app URL-encodes them. Don’t put raw `@` in `DATABASE_URL` unencoded |
| Images 404 in UI | Ensure API is up; Vite proxies `/media`. Restart `dev:web` after proxy changes |
| Generate 502 / OpenAI errors | Check key, image model, size, and org rate limits |
| Theme 401 loops | Refresh token expired — log in again |
| LinkedIn publish fails | Connect personal or company page; set client ID/secret and redirect URIs; company pages need Community Management API approval |
| Company page list empty | Admin must complete org OAuth; member needs ADMIN/CONTENT_ADMIN role on the page |
| Carousel publish error | Document upload requires Community Management; generate/preview still works |
| PDF generates immediately | Attach PDF stages a draft — add context and press Send (not auto-generate) |

---

## Security reminders

- Do not commit secrets (`.env` is gitignored).  
- Rotate any key that was shared in chat or screenshots.  
- Seed passwords are for **local/dev only**.  
- Tenant data is scoped by `tenant_id` on queries and media keys.

---

## License & ownership

Internal product of **TechPotato Softwares LLP**. See `apps/LICENSE` for framework-related licensing where applicable.

---

## Support

For product intent and deeper specs, start with the TRD/PRD under `Docs/` / `RequirementDocs/`. For day-to-day setup issues, use this README and ask the team for current Supabase + OpenAI access.
