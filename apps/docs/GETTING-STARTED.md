# Getting started — Python CloudArc

Copy the **`python-cloud-arc`** folder, then:

1. [ ] `cd` into your copied folder
2. [ ] `docker compose up -d`
3. [ ] `cp api/.env.example api/.env`
4. [ ] `cd api && python3 -m venv .venv && source .venv/bin/activate`
5. [ ] `pip install -e ".[dev]"`
6. [ ] Init DB (`init_db()` as in README, or Alembic)
7. [ ] `uvicorn src.dev_server:app --reload --port 4001`
8. [ ] Login + demo CRUD + `POST /api/ai/chat`
9. [ ] `python layers/shared/python/scripts/build_layer.py`
10. [ ] `cd ../cdk && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && cdk deploy ApiStack-dev`
11. [ ] Set `AI_PROVIDER` + keys only via env / Secrets Manager in prod
12. [ ] Read [SECURITY.md](SECURITY.md) and [LAYER-PARITY.md](LAYER-PARITY.md)

Full architecture: [ARCHITECTURE.md](ARCHITECTURE.md)
