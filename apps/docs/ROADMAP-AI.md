# Roadmap — AI feasibility

## Position

- **Python SKU** is the primary AI runtime (providers, LangChain hooks, pgvector).
- **Node SKU** ships a thin `/api/ai/chat` stub for parity.

## Compose already includes

`pgvector/pgvector:pg16` — ready for embeddings tables.

## Planned capabilities

| Capability | Target |
|------------|--------|
| Provider interface (OpenAI, Bedrock, Anthropic) | Python v1 (stub + env switch) — **done** |
| Embeddings table + pgvector index | v1.1 |
| RAG module (`modules/rag`) | v1.2 |
| Tool-calling / agents | v1.3 |
| Eval harness (prompt regression) | v2 |
| Streaming responses via API Gateway WebSocket / HTTP stream | v2 |

## Buyer guidance

Set `AI_PROVIDER=openai|bedrock|stub` and provider credentials. Do not ship API keys in the repo.
