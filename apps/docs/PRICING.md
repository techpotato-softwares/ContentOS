# Pricing & business model

## ContentOS SaaS plans (hybrid AI billing)

Canonical list prices live in `PLAN_CATALOG` (`utils/ai_billing.py`).

| Plan | USD / mo (Stripe) | INR / mo (Razorpay) | AI posts | BYOK |
|------|-------------------|---------------------|----------|------|
| Starter | $49 | ₹4,099 | 40 | No |
| Growth | $149 | ₹12,499 | 150 | Yes |
| Scale | $399 | ₹33,499 | 500 | Yes |
| Agency | $399 | ₹33,499 | 50 platform trial | Yes |

**USD ↔ INR:** fixed product mapping (~₹83–84 / USD), not live FX. Razorpay Dashboard plan amounts must match the INR column exactly.

See also: `FEATURE-HYBRID-AI-BILLING.md`, `STRIPE-BILLING.md`, `RAZORPAY-BILLING.md`.

---

## Recommended one-time SKUs (USD)

| SKU | Price | Includes |
|-----|-------|----------|
| **ArcForge Node** | **$349** | TS CloudArc: shared layer, platform, demo, AI stub, CDK, CI, docs; **12 months** updates |
| **ArcForge Python** | **$399** | Python CloudArc: mirrored layer, platform, demo, **AI providers**, CDK notes, CI, docs; **12 months** updates |
| **Bundle (Node + Python)** | **$599** | Both trees + API contract (save vs $748) |
| **Agency** | **$1,499** | Bundle + 5 seats + client-project redistribution + 1 architecture review call |
| **Enterprise** | **$4,000+** | Custom license, SSO/Cognito priority, private support SLA |

## Recurring

After included updates period:

- **$99/year** per single SKU, or
- **$149/year** Bundle updates

## Add-ons

| Add-on | Price |
|--------|-------|
| Setup / migration day | $800–$1,500 |
| Custom module workshop | $2,000+ |

## Why these prices

- Differentiator vs free SST tutorials: **productized dual kits**, RBAC guards, tenancy hook, commercial docs, pack scripts
- Python priced slightly higher for AI positioning
- Agency unlocks redistribution without undercutting kit sales

## Packaging for delivery

```bash
pnpm pack:node     # or bash scripts/pack-node.sh
pnpm pack:python
```

Deliver zip or private repo invite per license.
