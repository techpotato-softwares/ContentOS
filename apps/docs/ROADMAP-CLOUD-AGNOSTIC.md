# Roadmap — cloud-agnostic

Today ArcForge is **AWS-first** (Lambda, API Gateway, Secrets Manager, S3, CDK).

## Goal

Introduce a thin **CloudProvider** port so storage, secrets, functions, and queues can be swapped later.

```text
interfaces/
  secrets.py|ts
  object_storage.py|ts
  functions.py|ts
  queue.py|ts
adapters/
  aws/
  azure/   # later
  gcp/     # later
```

## Phases

1. **v1 (now):** Document interfaces; AWS only in code
2. **v1.1:** Extract S3 + Secrets behind interfaces in both Node and Python layers
3. **v2:** Azure Functions + Key Vault adapter (pilot)
4. **v2.1:** GCP Cloud Functions + Secret Manager

## Non-goals for v1

- Multi-cloud in one deploy
- Terraform dual-provider generators
