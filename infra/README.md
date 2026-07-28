# ContentOS Python CDK

Infrastructure for ContentOS API (Python Lambdas) + optional static web hosting.

```bash
cd apps/api && python layers/shared/python/scripts/build_layer.py
cd infra
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cdk synth ApiStack-dev
cdk deploy ApiStack-qa
```

- Local/QA DB: Supabase (`DB_SSL=true`) via Secrets Manager / `env.local.json`
- Prod: RDS when `features.rds=True`
- Lambdas: `contentos-py-{auth|tenants|agent|publishing}-{env}`
