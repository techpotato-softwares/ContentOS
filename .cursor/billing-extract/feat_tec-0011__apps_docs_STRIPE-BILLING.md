# Stripe Billing (test mode)

ContentOS uses **Stripe** for USD subscription billing (Checkout + Customer Portal + webhooks).
**Razorpay** remains the separate INR/UPI gateway (task 0014) ΓÇö do not mix gateways in one checkout flow.

## 1. Stripe Dashboard (test mode)

1. Create four recurring Prices (USD monthly) matching `PLAN_CATALOG`:
   - Starter ΓÇö $49
   - Growth ΓÇö $149
   - Scale ΓÇö $399
   - Agency ΓÇö $399 (or your chosen Agency price)
2. Copy each Price id (`price_ΓÇª`) into env / Secrets Manager.
3. Developers ΓåÆ API keys ΓåÆ copy **Secret key** (`sk_test_ΓÇª`).
4. Developers ΓåÆ Webhooks ΓåÆ Add endpoint:
   - URL: `https://<api-host>/api/billing/webhook` (local: use Stripe CLI)
   - Events:
     - `checkout.session.completed`
     - `customer.subscription.updated`
     - `customer.subscription.deleted`
     - `invoice.payment_failed`
     - `invoice.paid`
   - Copy **Signing secret** (`whsec_ΓÇª`).

## 2. Local env (`apps/api/.env`)

```env
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_STARTER=price_...
STRIPE_PRICE_GROWTH=price_...
STRIPE_PRICE_SCALE=price_...
STRIPE_PRICE_AGENCY=price_...
BILLING_FRONTEND_URL=http://localhost:5173
```

Forward webhooks locally:

```bash
stripe listen --forward-to localhost:4001/api/billing/webhook
```

Use the CLI-printed `whsec_ΓÇª` as `STRIPE_WEBHOOK_SECRET` while listening.

## 3. Secrets Manager (QA/Prod)

Secret id: `/{APP}/{env}/stripe` (wired by CDK as `STRIPE_SECRET_ID`).

JSON keys (same names as env):

- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PRICE_STARTER`
- `STRIPE_PRICE_GROWTH`
- `STRIPE_PRICE_SCALE`
- `STRIPE_PRICE_AGENCY`

After first CDK deploy, replace placeholder values in the console.

## 4. App behavior

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `POST /api/billing/checkout-session` | tenant-admin | Start Stripe Checkout for a plan |
| `POST /api/billing/portal-session` | tenant-admin | Open Customer Portal |
| `POST /api/billing/webhook` | public + Stripe signature | Sync plan / status |
| `GET /api/billing/summary` | tenant-admin | Plan + quota + CTAs |

- Price id ΓåÆ `PLAN_CATALOG` tier ΓåÆ `tenant.plan_tier` + `ai_posts_quota_monthly`.
- `invoice.payment_failed` / past-due / canceled ΓåÆ soft-lock **platform** AI generate with `402 billing_required`.
- **BYOK** (`ai_billing_mode=byok`) is **not** blocked by Stripe payment status.
- Webhook event ids are stored in `stripe_webhook_events` for idempotency.
- Never log secret keys or full webhook payloads.

## 5. Migration

```bash
cd apps/api
alembic upgrade head
```

Revision: `20260326_01_stripe_billing`.

## 6. UI

Settings ΓåÆ **Billing** (`/settings/billing`): Upgrade (Checkout) and Manage billing (Portal).
