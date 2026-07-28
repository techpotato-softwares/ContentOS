# Layer parity checklist (Node ↔ Python)

Keep this green before each release.

| Node (`node-cloud-arc/api/...`) | Python (`python-cloud-arc/api/...`) | Status |
|----------------------------------|-------------------------------------|--------|
| `layers/shared/nodejs/src/config/` | `layers/shared/python/src/config/` | OK |
| `layers/shared/nodejs/src/database/` | `layers/shared/python/src/database/` (+ `models.py`) | OK |
| `layers/shared/nodejs/src/decorators/` | `layers/shared/python/src/decorators/` | OK |
| `core/handler-factory.ts` | `core/handler_factory.py` | OK |
| `core/router.ts` | `core/router.py` | OK |
| `core/parameter-resolver.ts` | `core/parameter_resolver.py` | OK |
| `core/service-registry.ts` | `core/service_registry.py` | OK |
| `core/openapi/` | `core/openapi/` + FastAPI OpenAPI | OK |
| `middleware/authMiddleware.ts` | `middleware/auth.py` | OK |
| `middleware/errorHandler.ts` | `middleware/error_handler.py` | OK |
| `utils/logger.ts` | `utils/logger.py` | OK |
| `utils/secrets.ts` | `utils/secrets.py` | OK |
| `utils/jwt-secrets.ts` | `utils/jwt_secrets.py` | OK |
| `utils/webtoken.ts` | `utils/webtoken.py` | OK |
| `utils/s3.ts` | `utils/s3.py` | OK |
| Layer build script | `layers/shared/python/scripts/build_layer.py` | OK |
| `@RequirePermission` / `@RequireModule` | `auth_decorators.py` | OK |
| Express `src/dev-server.ts` | FastAPI `src/dev_server.py` | OK |
| `app-manifest.json` | `app-manifest.json` | OK |
| `modules/*/lambdas/*.lambda.ts` | `modules/*/lambdas/*.py` | OK |
| `cdk/` TypeScript CDK | `cdk/` **Python CDK** (`aws-cdk-lib`) | OK |

**Idiomatic note:** TypeScript uses `experimentalDecorators`; Python uses real decorators + a route registry. Behavior (CSR, cold-start cache, JWT gates) matches.
