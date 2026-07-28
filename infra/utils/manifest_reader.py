"""Read api/app-manifest.json for Lambda/API Gateway wiring."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from paths import MANIFEST_PATH


@dataclass
class RouteManifestEntry:
    method: str
    path: str
    controller: str
    action: str


@dataclass
class LambdaManifestEntry:
    handler: str
    controller: str
    routes: list[RouteManifestEntry] = field(default_factory=list)


@dataclass
class AppManifest:
    version: str
    generated_at: str
    lambdas: dict[str, LambdaManifestEntry] = field(default_factory=dict)


def _parse_lambda(raw: dict[str, Any]) -> LambdaManifestEntry:
    routes = [
        RouteManifestEntry(
            method=r["method"],
            path=r["path"],
            controller=r["controller"],
            action=r["action"],
        )
        for r in raw.get("routes", [])
    ]
    return LambdaManifestEntry(
        handler=raw["handler"],
        controller=raw.get("controller", ""),
        routes=routes,
    )


def read_manifest() -> AppManifest:
    if not MANIFEST_PATH.exists():
        print(f"⚠️  Warning: app-manifest.json not found at {MANIFEST_PATH}")
        print("   Ensure api/app-manifest.json exists (hand-maintained in the Python kit).")
        print("   Using default empty manifest.\n")
        return AppManifest(
            version="1.0",
            generated_at=datetime.now(timezone.utc).isoformat(),
            lambdas={},
        )

    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    lambdas = {
        name: _parse_lambda(cfg) for name, cfg in data.get("lambdas", {}).items()
    }
    manifest = AppManifest(
        version=str(data.get("version", "1.0")),
        generated_at=str(data.get("generatedAt", "")),
        lambdas=lambdas,
    )
    print(f"📄 Loaded app-manifest.json (v{manifest.version})")
    print(f"   Generated: {manifest.generated_at}")
    print(f"   Lambdas: {len(manifest.lambdas)}")
    return manifest


def get_routes_for_lambda(
    manifest: AppManifest, lambda_name: str
) -> list[RouteManifestEntry]:
    entry = manifest.lambdas.get(lambda_name)
    return entry.routes if entry else []


def get_lambda_names(manifest: AppManifest) -> list[str]:
    return list(manifest.lambdas.keys())
