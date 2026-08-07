# Feature brief: Hybrid AI billing (platform keys + BYOK)

**Status:** Ready for implementation  
**Owner:** ContentOS product / backend  
**Audience:** Engineer implementing the feature  
**Related discussion:** Platform-included AI vs white-label BYOK → **hybrid recommended**

---

## 1. Goal

Support two AI cost models under one product:

| Mode | Who pays OpenAI/Gemini | What ContentOS charges |
|------|------------------------|-------------------------|
| **`platform`** (default) | We do (our API keys) | SaaS plan + included AI quota + overages |
| **`byok`** | The tenant (their keys) | Higher platform / agency fee only (no AI COGS on us) |

Long-term monetization: **platform mode is the default revenue engine**; **BYOK is an unlock for Growth+ / Agency / Enterprise**.

---

## 2. Product rules

1. New tenants start on **`ai_billing_mode = platform`** and a plan tier (default **`starter`**).
2. In **platform** mode, all agent/text/image calls use **platform secrets** (`/contentos/{env}/ai`).
3. In **byok** mode, calls use **tenant-stored keys**; if keys are missing, return a clear `400` (not a 500 config error).
4. **Never** return raw API keys in API responses. Only booleans like `openaiConfigured: true`.
5. **Never** put API keys in `environment.py`, Git, or Lambda plain env in QA/Prod. Secrets Manager only (local `.env` OK for `IS_LOCAL=true`).
6. Platform usage is **metered** (monthly AI post quota). BYOK usage is logged for analytics but **does not consume** platform quota.
7. BYOK should only be allowed when plan allows it (`growth`, `scale`, `agency`) — enforce in API; UI can hide/disable the toggle otherwise.

---

## 3. Suggested pricing (product copy; wire as plan config)

Use these as defaults in code (`PLAN_CATALOG`), not hard-coded magic numbers scattered in controllers.

| Plan | Monthly (USD) | Included AI posts/mo | BYOK allowed |
|------|---------------|----------------------|--------------|
| **Starter** | $49 | 40 | No |
| **Growth** | $149 | 150 | Yes (+$79/mo add-on **or** included — product choice; start with **included on Growth+**) |
| **Scale** | $399 | 500 | Yes |
| **Agency** | $299–$499 | 0 on platform (BYOK required) or small trial quota | Yes (required) |

Overage (platform only): e.g. Starter **+$15 / 25 posts**, Growth **+$40 / 100 posts** (config table; Stripe later).

Annual: ~2 months free (billing integration later — out of scope for v1).

---

## 4. Current codebase gaps (read before coding)

| Area | Today | Needed |
|------|--------|--------|
| Keys | `OPENAI_API_KEY` / `GEMINI_API_KEY` from **process env only** (`providers.py`, `image_providers.py`) | Resolve per-tenant: platform SM **or** tenant BYOK |
| Tenant model | No billing/AI fields (`models.py` `Tenant`) | Mode, plan, secret ARN, quota counters |
| CDK | Models/flags on Lambda; **keys not wired** for QA/Prod | Platform AI secret construct + `AI_SECRET_ID` |
| Settings API | Training/theme only | `GET/PUT /api/tenants/me/ai-settings` |
| Web UI | Training under Settings | New **AI & billing** settings page |
| Metering | None | Quota check + usage events on generate |

**There is no `environment.ts`.** Deploy config is Python: `infra/config/environment.py`.

Key insertion points:

- `apps/api/modules/agent/src/providers.py` → `get_provider()`, `OpenAIProvider`, `GeminiProvider`
- `apps/api/modules/agent/src/image_providers.py` → `get_image_provider()`, `OpenAIImageProvider`
- `apps/api/modules/agent/src/controllers/agent_controller.py` → chat / generate / insights / score
- `apps/api/modules/tenants/src/controllers/tenants_controller.py` + `app-manifest.json`
- `apps/api/layers/shared/python/src/database/models.py`
- `infra/cdk_constructs/core/lambda_construct.py` + new secrets construct
- Web: `contentApi.ts`, `AppShell.tsx`, `router.tsx`, new settings page

Mirror secrets pattern from: `apps/api/layers/shared/python/src/utils/jwt_secrets.py`.

---

## 5. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Agent / image call (tenant_id known from JWT)              │
└────────────────────────────┬────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────┐
│  resolve_ai_credentials(tenant)                             │
│    mode=platform → Secrets Manager /contentos/{env}/ai      │
│                    (local: apps/api/.env)                   │
│    mode=byok     → Secrets Manager                          │
│                    /contentos/{env}/tenants/{id}/ai         │
│                    (local: encrypted blob / local stub OK)  │
└────────────────────────────┬────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────┐
│  if mode=platform: assert_and_consume_quota(tenant, n)      │
│  get_provider(name, api_keys=...)                           │
│  get_image_provider(model, api_keys=...)                    │
│  record AiUsageEvent                                        │
└─────────────────────────────────────────────────────────────┘
```

### Secret payloads

**Platform** — `/contentos/{env}/ai`:

```json
{
  "OPENAI_API_KEY": "...",
  "GEMINI_API_KEY": "...",
  "AI_PROVIDER": "openai"
}
```

**Tenant BYOK** — `/contentos/{env}/tenants/{tenantId}/ai`:

```json
{
  "OPENAI_API_KEY": "...",
  "GEMINI_API_KEY": "..."
}
```

Store ARN (or secret name) on `tenants.ai_secret_arn`. IAM already allows Get/Put on `/{APP_NAME}/*` in Lambda role — confirm and extend if needed.

---

## 6. Data model

### `tenants` — new columns

| Column | Type | Default | Notes |
|--------|------|---------|--------|
| `ai_billing_mode` | `VARCHAR` | `'platform'` | `platform` \| `byok` |
| `plan_tier` | `VARCHAR` | `'starter'` | `starter` \| `growth` \| `scale` \| `agency` |
| `ai_secret_arn` | `VARCHAR` NULL | null | BYOK secret name/ARN |
| `ai_posts_quota_monthly` | `INT` | from plan catalog | Snapshot; can override per tenant |
| `ai_posts_used_month` | `INT` | `0` | Reset when month changes |
| `ai_usage_month` | `VARCHAR` NULL | null | `YYYY-MM` for reset |

Do **not** put keys in `training_json`.

### New table `ai_usage_events` (recommended)

| Column | Type |
|--------|------|
| `event_id` | PK |
| `tenant_id` | FK |
| `user_id` | nullable |
| `billing_mode` | `platform` \| `byok` |
| `event_type` | e.g. `generate_batch`, `chat`, `score` |
| `units` | int (e.g. number of posts generated) |
| `provider` | openai/gemini/bedrock/stub |
| `detail` | TEXT JSON optional |
| `created_at` | timestamp |

### Schema apply

Prefer:

1. Update SQLModel in `models.py`
2. `_ensure_tenant_ai_columns()` (same pattern as `_ensure_layout_column` / social accounts) for existing Supabase DBs
3. Optional first Alembic revision under `apps/api/alembic/versions/` for prod discipline

---

## 7. Backend work packages

### WP1 — Platform AI secrets (infra)

1. Add `AiSecretsConstruct` (similar to JWT/DB secrets):
   - Secret name: `/{APP}/qa/ai`, `/{APP}/prod/ai`
   - Generate placeholder or create empty template keys `OPENAI_API_KEY`, `GEMINI_API_KEY` for manual fill after first deploy
2. Wire `AI_SECRET_ID` into Lambda environment in `lambda_construct.py`
3. Document: after QA deploy, paste real keys into Secrets Manager (do not commit `.env` keys)
4. Local: keep using `apps/api/.env`

### WP2 — Shared AI credential + billing helpers

New modules under shared layer, e.g.:

- `utils/ai_secrets.py`
  - `get_platform_ai_secrets() -> dict`
  - `get_tenant_ai_secrets(tenant_id, secret_arn) -> dict`
  - `put_tenant_ai_secrets(tenant_id, keys) -> secret_arn` (create/update SM; local stub OK)
- `utils/ai_billing.py`
  - `PLAN_CATALOG` with quotas + `byok_allowed`
  - `resolve_ai_credentials(tenant) -> ResolvedAiCredentials`
  - `ensure_monthly_quota(tenant, units) -> None` raises `ValidationError` / `QUOTA_EXCEEDED` when platform over limit
  - `record_usage(...)`

`ResolvedAiCredentials` should include: `mode`, `openai_api_key`, `gemini_api_key`, `source` (`platform`|`byok`|`env`).

### WP3 — Provider factory

Change constructors to accept optional overrides:

```python
OpenAIProvider(api_key: str | None = None)
GeminiProvider(api_key: str | None = None)
OpenAIImageProvider(model_id: str = "...", api_key: str | None = None)

def get_provider(name: str | None = None, *, api_keys: dict | None = None) -> AIProvider
def get_image_provider(model_id: str | None = None, *, api_keys: dict | None = None) -> ImageBackgroundProvider
```

Fallback order: explicit override → env (local/platform already loaded into env by helper if desired).

Update `list_text_providers` / image model availability to consider **resolved** keys for the current tenant when called from authenticated endpoints.

### WP4 — Agent call sites

In `agent_controller.py` (chat, generate, insights, score, etc.):

1. Load `Tenant`
2. `creds = resolve_ai_credentials(tenant)`
3. For billable actions (especially **generate**): `ensure_monthly_quota(tenant, units=len(variants))` when `mode == platform`
4. `provider = get_provider(ai_name, api_keys=creds.as_dict())`
5. `img_provider = get_image_provider(..., api_keys=creds.as_dict())`
6. On success: increment `ai_posts_used_month` + `record_usage`

Define clearly what counts as **1 AI post unit** (recommendation: **one generated variant/post** in a generate batch; chat/score optional lighter metering or free within plan — product can start with **generate only**).

### WP5 — Tenant AI settings API

Add to `TenantsController` + `app-manifest.json`:

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/tenants/me/ai-settings` | Mode, plan, quota used/limit, `openaiConfigured`, `geminiConfigured`, `byokAllowed` — **no secrets** |
| `PUT` | `/api/tenants/me/ai-settings` | Body: `{ "aiBillingMode"?, "openaiApiKey"?, "geminiApiKey"?, "clearOpenai"?, "clearGemini"? }` |

Permissions: tenant admin / same as training update (reuse existing auth patterns). Super-admin may need `PUT /api/admin/tenants/{tenantId}/ai-settings` later; v1 can be **me** only + plan changes via admin later.

Validation:

- Switching to `byok` without any key → 400
- Switching to `byok` when plan disallows → 403
- Empty string key → ignore or clear; never store plaintext in DB

### WP6 — Web UI

1. Route: `/settings/ai` (under protected shell)
2. Nav link in `AppShell` next to Training
3. Page sections:
   - Current plan + quota progress (platform)
   - Mode toggle: Platform included AI vs Bring your own keys
   - BYOK: password inputs for OpenAI / Gemini + Save (show “Configured” badges)
   - Short copy explaining cost responsibility
4. RTK Query endpoints in `contentApi.ts`

---

## 8. API response shapes (contract)

### `GET /api/tenants/me/ai-settings`

```json
{
  "success": true,
  "data": {
    "aiBillingMode": "platform",
    "planTier": "starter",
    "byokAllowed": false,
    "quota": {
      "monthlyLimit": 40,
      "usedThisMonth": 12,
      "month": "2026-08",
      "remaining": 28
    },
    "keys": {
      "openaiConfigured": false,
      "geminiConfigured": false
    },
    "plans": [
      { "id": "starter", "label": "Starter", "monthlyUsd": 49, "quota": 40, "byokAllowed": false },
      { "id": "growth", "label": "Growth", "monthlyUsd": 149, "quota": 150, "byokAllowed": true }
    ]
  }
}
```

### `PUT /api/tenants/me/ai-settings` (example)

```json
{
  "aiBillingMode": "byok",
  "openaiApiKey": "sk-...",
  "geminiApiKey": ""
}
```

Response: same shape as GET (without echoing keys).

### Errors

| Code | When |
|------|------|
| `QUOTA_EXCEEDED` | Platform mode, monthly limit hit |
| `BYOK_NOT_ALLOWED` | Plan cannot use BYOK |
| `BYOK_KEYS_MISSING` | Mode is byok but no usable key for requested provider |
| `AI_CONFIG` | Platform secret missing in non-local env |

---

## 9. Security checklist

- [ ] Keys never in logs (redact)
- [ ] Keys never in API responses or audit `detail` plaintext
- [ ] Secrets Manager encryption; least-privilege IAM
- [ ] Rotate guidance in README after any key leaked via `.env` / chat
- [ ] UI uses `type="password"`; placeholders only
- [ ] CSRF/auth same as other tenant mutating routes

---

## 10. Out of scope for v1 (do later)

- Stripe / Razorpay checkout and automatic plan upgrades
- Real overage invoices
- Per-seat billing
- Admin UI to change another tenant’s plan (can be SQL/seed for now)
- Bedrock as BYOK (platform IAM only for now)
- White-label custom domain packaging beyond existing `ui_mode`

---

## 11. Implementation order (for junior)

1. **Model + `_ensure_*` columns** + `PLAN_CATALOG`
2. **`ai_secrets` + `ai_billing` helpers** (unit-testable)
3. **Provider override args** + agent_controller wiring + quota on generate
4. **Tenant AI settings GET/PUT** + manifest routes
5. **CDK platform AI secret** + `AI_SECRET_ID`
6. **Web settings page**
7. **Manual test script** (below)
8. Short update to `apps/docs/PRICING.md` / SECURITY note

---

## 12. Test plan

### Local

1. `.env` has platform OpenAI key; tenant mode `platform` → generate works; `ai_posts_used_month` increments.
2. Hit quota (set limit to 1) → next generate returns `QUOTA_EXCEEDED`.
3. Switch tenant to `byok` with invalid plan (`starter`) → `BYOK_NOT_ALLOWED`.
4. Set plan `growth`, mode `byok`, save OpenAI key → generate works; usage event `billing_mode=byok`; quota **unchanged**.
5. BYOK with empty keys → clear `BYOK_KEYS_MISSING`.
6. GET settings never contains `sk-` strings.

### QA (after deploy)

1. Create/update `/contentos/qa/ai` with real keys.
2. Confirm Lambdas have `AI_SECRET_ID`.
3. Platform generate on QA tenant works without keys in Lambda console env.
4. BYOK path writes `/contentos/qa/tenants/{id}/ai` and reads it back.

---

## 13. Acceptance criteria

- [ ] Hybrid modes work end-to-end locally and on QA
- [ ] Platform keys only from SM (QA/Prod) or `.env` (local)
- [ ] Tenant can configure BYOK from UI when plan allows
- [ ] Platform quota enforced on generate
- [ ] No raw keys in responses, logs, or git
- [ ] Docs updated (`PRICING.md` SaaS section + this brief linked from README/infra README if useful)

---

## 14. Reference file map

| Concern | Path |
|---------|------|
| Tenant model | `apps/api/layers/shared/python/src/database/models.py` |
| JWT SM pattern | `apps/api/layers/shared/python/src/utils/jwt_secrets.py` |
| Providers | `apps/api/modules/agent/src/providers.py` |
| Images | `apps/api/modules/agent/src/image_providers.py` |
| Agent API | `apps/api/modules/agent/src/controllers/agent_controller.py` |
| Tenants API | `apps/api/modules/tenants/src/controllers/tenants_controller.py` |
| Routes | `apps/api/app-manifest.json` |
| CDK Lambdas | `infra/cdk_constructs/core/lambda_construct.py` |
| Env config | `infra/config/environment.py` |
| Web API client | `apps/web/src/features/api/contentApi.ts` |
| Router / nav | `apps/web/src/app/router.tsx`, `shared/layout/AppShell.tsx` |

---

## 15. Decision log

| Decision | Choice |
|----------|--------|
| Business model | **Hybrid** (platform default + BYOK for higher plans) |
| Primary profit lever | Platform included AI + overages |
| BYOK role | Agency / enterprise unlock, lower COGS risk |
| Config language | Python `environment.py` (not TypeScript) |
| Secret store | AWS Secrets Manager |
| v1 metering unit | Generated content posts (generate batch variants) |
| Stripe | Deferred |

Questions while implementing → ask tech lead before changing plan catalog prices or what counts as a billable unit.
