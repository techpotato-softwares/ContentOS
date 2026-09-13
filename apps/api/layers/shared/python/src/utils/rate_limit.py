"""Auth endpoint rate limiting: Redis token bucket → DynamoDB → Postgres → memory."""
from __future__ import annotations

import os
import threading
import time
from typing import Protocol

from middleware.error_handler import RateLimitError
from utils.logger import logger


def _capacity() -> float:
    return float(os.environ.get("AUTH_RATE_LIMIT_CAPACITY", "10"))


def _refill_per_sec() -> float:
    # Default: ~10 tokens / 60s → refill 1/6 per second
    return float(os.environ.get("AUTH_RATE_LIMIT_REFILL_PER_SEC", str(10 / 60)))


def client_ip_from_event(event: dict | None) -> str:
    if not event:
        return "unknown"
    headers = event.get("headers") or {}
    # API Gateway may lowercase headers
    lowered = {str(k).lower(): v for k, v in headers.items()}
    forwarded = lowered.get("x-forwarded-for") or lowered.get("x-real-ip")
    if forwarded:
        return str(forwarded).split(",")[0].strip() or "unknown"
    req_ctx = event.get("requestContext") or {}
    identity = req_ctx.get("identity") or {}
    return str(identity.get("sourceIp") or "unknown")


def auth_rate_limit_key(action: str, *, identity: str, event: dict | None = None) -> str:
    ip = client_ip_from_event(event)
    ident = (identity or "").strip().lower() or "-"
    return f"auth:{action}:{ip}:{ident}"


class _BucketStore(Protocol):
    def take(self, key: str, *, capacity: float, refill_per_sec: float, cost: float = 1.0) -> bool:
        ...


class _MemoryStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._buckets: dict[str, tuple[float, float]] = {}

    def take(self, key: str, *, capacity: float, refill_per_sec: float, cost: float = 1.0) -> bool:
        now = time.time()
        with self._lock:
            tokens, updated = self._buckets.get(key, (capacity, now))
            tokens = min(capacity, tokens + (now - updated) * refill_per_sec)
            if tokens < cost:
                self._buckets[key] = (tokens, now)
                return False
            self._buckets[key] = (tokens - cost, now)
            return True

    def clear(self) -> None:
        with self._lock:
            self._buckets.clear()


_memory = _MemoryStore()


class _RedisStore:
    def __init__(self, url: str) -> None:
        import redis  # optional dependency

        self._client = redis.from_url(url, decode_responses=True)

    def take(self, key: str, *, capacity: float, refill_per_sec: float, cost: float = 1.0) -> bool:
        # Lua token bucket: KEYS[1]=key ARGV=capacity, refill, cost, now
        script = """
        local key = KEYS[1]
        local capacity = tonumber(ARGV[1])
        local refill = tonumber(ARGV[2])
        local cost = tonumber(ARGV[3])
        local now = tonumber(ARGV[4])
        local data = redis.call('HMGET', key, 'tokens', 'updated')
        local tokens = tonumber(data[1])
        local updated = tonumber(data[2])
        if tokens == nil then
          tokens = capacity
          updated = now
        end
        tokens = math.min(capacity, tokens + (now - updated) * refill)
        if tokens < cost then
          redis.call('HMSET', key, 'tokens', tokens, 'updated', now)
          redis.call('EXPIRE', key, 3600)
          return 0
        end
        tokens = tokens - cost
        redis.call('HMSET', key, 'tokens', tokens, 'updated', now)
        redis.call('EXPIRE', key, 3600)
        return 1
        """
        ok = self._client.eval(script, 1, key, capacity, refill_per_sec, cost, time.time())
        return bool(int(ok))


class _DynamoStore:
    def __init__(self, table_name: str) -> None:
        import boto3

        self._table = boto3.resource("dynamodb").Table(table_name)

    def take(self, key: str, *, capacity: float, refill_per_sec: float, cost: float = 1.0) -> bool:
        from decimal import Decimal

        now = time.time()
        try:
            resp = self._table.get_item(Key={"pk": key})
            item = resp.get("Item") or {}
            tokens = float(item.get("tokens", capacity))
            updated = float(item.get("updated", now))
        except Exception as exc:
            logger.warn("Dynamo rate-limit read failed; denying conservatively", {"error": str(exc)})
            return False
        tokens = min(capacity, tokens + (now - updated) * refill_per_sec)
        if tokens < cost:
            self._table.put_item(
                Item={
                    "pk": key,
                    "tokens": Decimal(str(round(tokens, 6))),
                    "updated": Decimal(str(now)),
                }
            )
            return False
        tokens -= cost
        self._table.put_item(
            Item={
                "pk": key,
                "tokens": Decimal(str(round(tokens, 6))),
                "updated": Decimal(str(now)),
            }
        )
        return True


class _PostgresStore:
    def take(self, key: str, *, capacity: float, refill_per_sec: float, cost: float = 1.0) -> bool:
        from sqlalchemy import text
        from database import get_session

        now = time.time()
        with get_session() as session:
            session.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS auth_rate_buckets (
                        bucket_key TEXT PRIMARY KEY,
                        tokens DOUBLE PRECISION NOT NULL,
                        updated_at DOUBLE PRECISION NOT NULL
                    )
                    """
                )
            )
            row = session.execute(
                text(
                    "SELECT tokens, updated_at FROM auth_rate_buckets WHERE bucket_key = :k FOR UPDATE"
                ),
                {"k": key},
            ).first()
            if row is None:
                tokens, updated = capacity, now
            else:
                tokens, updated = float(row[0]), float(row[1])
            tokens = min(capacity, tokens + (now - updated) * refill_per_sec)
            allowed = tokens >= cost
            if allowed:
                tokens -= cost
            session.execute(
                text(
                    """
                    INSERT INTO auth_rate_buckets (bucket_key, tokens, updated_at)
                    VALUES (:k, :t, :u)
                    ON CONFLICT (bucket_key) DO UPDATE
                    SET tokens = EXCLUDED.tokens, updated_at = EXCLUDED.updated_at
                    """
                ),
                {"k": key, "t": tokens, "u": now},
            )
            session.commit()
            return allowed


_store: _BucketStore | None = None
_store_name: str | None = None


def _resolve_store() -> tuple[_BucketStore, str]:
    global _store, _store_name
    if _store is not None and _store_name is not None:
        return _store, _store_name

    redis_url = (os.environ.get("REDIS_URL") or "").strip()
    if redis_url:
        try:
            _store = _RedisStore(redis_url)
            _store_name = "redis"
            return _store, _store_name
        except Exception as exc:
            logger.warn("Redis rate-limit unavailable; trying fallback", {"error": str(exc)})

    table = (os.environ.get("RATE_LIMIT_TABLE") or os.environ.get("AUTH_RATE_LIMIT_TABLE") or "").strip()
    if table:
        try:
            _store = _DynamoStore(table)
            _store_name = "dynamodb"
            return _store, _store_name
        except Exception as exc:
            logger.warn("Dynamo rate-limit unavailable; trying fallback", {"error": str(exc)})

    # Prefer Postgres when not forced to memory (tests set AUTH_RATE_LIMIT_STORE=memory)
    forced = (os.environ.get("AUTH_RATE_LIMIT_STORE") or "").strip().lower()
    if forced == "memory":
        _store = _memory
        _store_name = "memory"
        return _store, _store_name

    if forced != "memory":
        try:
            from database import get_engine

            get_engine()
            _store = _PostgresStore()
            _store_name = "postgres"
            return _store, _store_name
        except Exception as exc:
            logger.warn("Postgres rate-limit unavailable; using memory", {"error": str(exc)})

    _store = _memory
    _store_name = "memory"
    return _store, _store_name


def reset_rate_limit_store_for_tests() -> None:
    global _store, _store_name
    _store = None
    _store_name = None
    _memory.clear()


def enforce_auth_rate_limit(action: str, *, identity: str, event: dict | None = None) -> None:
    """Consume one token for login/register. Raises RateLimitError (HTTP 429) when empty."""
    key = auth_rate_limit_key(action, identity=identity, event=event)
    store, name = _resolve_store()
    capacity = _capacity()
    refill = _refill_per_sec()
    try:
        allowed = store.take(key, capacity=capacity, refill_per_sec=refill, cost=1.0)
    except Exception as exc:
        logger.warn("Rate-limit backend error; failing open for availability", {"store": name, "error": str(exc)})
        return
    if not allowed:
        raise RateLimitError("Too many attempts. Try again later.")
