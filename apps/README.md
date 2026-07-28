# Python CloudArc (`python-cloud-arc`)

**Copy this entire folder** to start a new Python / AWS serverless backend project.

You do **not** need `node-cloud-arc` or anything else from the monorepo.

## What’s inside

```text
python-cloud-arc/
├── README.md              ← you are here
├── docker-compose.yml     ← Postgres (+ Redis, pgvector)
├── package.json           ← convenience scripts from this folder
├── docs/                  ← architecture, security, getting started
├── api/                   ← Lambda host, shared layer, modules
│   ├── layers/shared/python/
│   ├── modules/{platform,demo,ai}/lambdas/
│   ├── src/dev_server.py  ← FastAPI local API on :4001
│   ├── app-manifest.json  ← CDK wires routes from this
│   └── .env.example
└── cdk/                   ← AWS CDK in **Python** (api gateway, lambdas, etc.)
```

## Start a new project

```bash
# 1. Copy the kit
cp -R python-cloud-arc ~/Projects/my-python-backend
cd ~/Projects/my-python-backend

# 2. Infra + env
docker compose up -d
cp api/.env.example api/.env

# 3. Install
cd api
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 4. Create tables
python -c "import os,sys; os.environ['IS_LOCAL']='true'; sys.path.insert(0,'layers/shared/python/src'); from database import init_db; import database.models; init_db()"

# 5. Run local API
uvicorn src.dev_server:app --reload --port 4001
# → http://localhost:4001
```

Or from the kit root:

```bash
npm run install:api
npm run dev
```

## Docs (read in order)

1. [docs/GETTING-STARTED.md](docs/GETTING-STARTED.md)
2. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
3. [docs/API-CONTRACT.md](docs/API-CONTRACT.md)
4. [docs/SECURITY.md](docs/SECURITY.md)
5. [docs/LAYER-PARITY.md](docs/LAYER-PARITY.md)
6. [docs/ROADMAP-AI.md](docs/ROADMAP-AI.md)

Also: [api/README.md](api/README.md) · [docs/PRICING.md](docs/PRICING.md) · [LICENSE](LICENSE) · [api/CHANGELOG.md](api/CHANGELOG.md)

## Tests

```bash
cd api && source .venv/bin/activate && pytest
```

## Deploy

Python CDK (`aws-cdk-lib`) — same stack/construct architecture as the Node kit:

```bash
cd api
python layers/shared/python/scripts/build_layer.py
cd ../cdk
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# CDK CLI still needs Node: npm i -g aws-cdk   (or use npx cdk)
cdk synth ApiStack-dev
cdk deploy ApiStack-dev
# or: ./scripts/deploy.sh dev
```

Handlers come from [`api/app-manifest.json`](api/app-manifest.json).

## Product

Sold as **ArcForge for Python**. Sibling kit: `../node-cloud-arc` (optional, separate purchase).
