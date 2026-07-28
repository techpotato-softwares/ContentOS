"""ContentOS API (Python CloudArc)

```bash
cp .env.example .env   # set Supabase + keys
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
python scripts/seed.py
uvicorn src.dev_server:app --reload --port 4001
```

Modules: `platform` (auth), `tenants` (training/theme), `agent` (chat/generate), `publishing` (LinkedIn + review gate).
"""
