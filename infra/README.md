# ContentOS Python CDK

Infrastructure for ContentOS API (Python Lambdas) + static hosting.

## Environments

| Env | Database | Secrets |
|-----|----------|---------|
| **dev / QA** | Shared Supabase (`features.rds=False`) | CDK creates `/contentos/{env}/db` + `/contentos/{env}/jwt`. **Update the DB password in Secrets Manager** to your Supabase password after first deploy. |
| **prod** | Amazon RDS PostgreSQL (`features.rds=True`) | CDK creates RDS + `/contentos/prod/db` (auto password) + JWT secret. |

Config source of truth: [`config/environment.py`](config/environment.py) (not TypeScript).

## URLs

| Path | Content |
|------|---------|
| `/` | Marketing site (`apps/marketing` static export) |
| `/app/` | Product SPA (`apps/web` built with `VITE_BASE=/app/`) |

## Local deploy

```bash
# One-time: Python >= 3.10, AWS creds, CDK bootstrap
npm run install:api
npm run install:web
npm run install:marketing
npm run install:infra
cd infra && source .venv/bin/activate
npx aws-cdk bootstrap

# From repo root
npm run deploy:qa    # or deploy:dev / deploy:prod
```

After first **QA** deploy, open AWS Secrets Manager → `/contentos/qa/db` → set `password` to the Supabase DB password.

## GitHub Actions

Workflows:

- [`.github/workflows/deploy-qa.yml`](../.github/workflows/deploy-qa.yml) — push to `main` or manual
- [`.github/workflows/deploy-prod.yml`](../.github/workflows/deploy-prod.yml) — tag `v*` or manual
- Shared logic: [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml)

### GitHub secrets (required)

| Secret | Where |
|--------|--------|
| `AWS_ACCESS_KEY_ID` | Repository or Environment (`qa` / `prod`) |
| `AWS_SECRET_ACCESS_KEY` | Repository or Environment (`qa` / `prod`) |

Create GitHub Environments named **`qa`** and **`prod`** (optional protection rules on prod).

### Optional GitHub Variables

Defaults come from `infra/config/environment.py`. Override per environment if needed:

| Variable | Purpose |
|----------|---------|
| `AWS_REGION` | Default `ap-south-1` |
| `DB_HOST` | Supabase host for QA/dev |
| `DB_NAME` | DB name (default `postgres` / prod `contentos`) |
| `DB_USERNAME` | DB user (default `postgres`) |
| `CUSTOM_DOMAIN` | Prod CloudFront alias |
| `CLOUDFRONT_CERTIFICATE_ARN` | ACM cert in `us-east-1` for custom domain |
| `SES_FROM_EMAIL` / `FROM_EMAIL` | Auth verify/reset + weekly snapshot from-address |
| `FRONTEND_URL` | Base URL for email verification / password-reset links |
| `SES_ENABLED` | `true` in deployed envs so Lambdas send via SES |

IAM user for the access key needs rights for CloudFormation, CDK bootstrap assets, Lambda, API Gateway, S3, CloudFront, Secrets Manager, IAM, and (prod) EC2/RDS/VPC.

## Stack outputs

- `ContentOSApiUrl-{env}` — API Gateway URL (baked into the SPA via `publish-web.sh`)
- `ContentOS-UI-URL-{env}` — Marketing (`/`)
- `ContentOS-App-URL-{env}` — Application (`/app/`)
- `ContentOSDbSecretArn-{env}` — QA/dev DB secret (not used on prod; RDS owns that secret)

Lambdas: `contentos-py-{auth|tenants|agent|publishing}-{env}`
