# Razorpay Billing (INR / UPI)

ContentOS uses **Razorpay** for INR subscriptions (Checkout short URL + payment links + webhooks).
**Stripe** remains the USD gateway. A tenant may have **only one active gateway** at a time.

## 1. Razorpay Dashboard (test mode)

1. Create four **Plans** (INR monthly) matching `PLAN_CATALOG.monthly_inr` exactly:
   - Starter — **₹4,099**
   - Growth — **₹12,499**
   - Scale — **₹33,499**
   - Agency — **₹33,499**
2. Copy each Plan id (`plan_…`) into env / Secrets Manager.
3. Settings → API Keys → copy **Key Id** + **Key Secret** (test).
4. Settings → Webhooks → Add endpoint:
   - URL: `https://<api-host>/api/billing/razorpay/webhook`
   - Events (minimum):
     - `subscription.activated`
     - `subscription.charged`
     - `subscription.updated`
     - `subscription.pending`
     - `subscription.halted`
     - `subscription.cancelled`
     - `payment.failed`
     - `payment.captured`
     - `payment_link.paid`
   - Copy **Webhook secret**.
5. Enable **UPI** + **Cards** on the Checkout / payment methods settings.

## 2. Local env (`apps/api/.env`, only when `IS_LOCAL=true`)

```env
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=...
RAZORPAY_WEBHOOK_SECRET=...
RAZORPAY_PLAN_STARTER=plan_...
RAZORPAY_PLAN_GROWTH=plan_...
RAZORPAY_PLAN_SCALE=plan_...
RAZORPAY_PLAN_AGENCY=plan_...
BILLING_FRONTEND_URL=http://localhost:5173
```

Never put these values in frontend env (`VITE_*`) or CDK plain env beyond `RAZORPAY_SECRET_ID`.

## 3. Secrets Manager (QA/Prod)

Secret id: `/{APP}/{env}/razorpay` (CDK injects `RAZORPAY_SECRET_ID` only).

JSON keys:

- `RAZORPAY_KEY_ID`
- `RAZORPAY_KEY_SECRET`
- `RAZORPAY_WEBHOOK_SECRET`
- `RAZORPAY_PLAN_STARTER`
- `RAZORPAY_PLAN_GROWTH`
- `RAZORPAY_PLAN_SCALE`
- `RAZORPAY_PLAN_AGENCY`

## 4. App behavior

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `POST /api/billing/razorpay/subscription` | tenant-admin | Create subscription + Checkout URL |
| `POST /api/billing/razorpay/payment-link` | tenant-admin | INR payment link (UPI + cards) |
| `POST /api/billing/razorpay/cancel` | tenant-admin | Cancel subscription |
| `POST /api/billing/razorpay/webhook` | public + signature | Sync plan / status |
| `GET /api/billing/summary?currency=inr` | tenant-admin | Preferred gateway = razorpay |

- Plan id / notes → `PLAN_CATALOG` → `plan_tier` + quota.
- Failed / halted / pending → `billing_status=past_due` → same soft-lock as Stripe (`402 billing_required`).
- Webhook event ids stored in `razorpay_webhook_events` (idempotent).
- Active Stripe subscription blocks Razorpay create (and vice versa).

## 5. Migration

```bash
cd apps/api
alembic upgrade head
```

Revision: `20260327_01_razorpay_billing` (after Stripe billing revision).
Local/SQLite also uses `ensure_tenant_billing_columns()`.
