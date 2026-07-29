"""EventBridge weekly team performance snapshot (Amazon SES)."""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "layers" / "shared" / "python" / "src"))
sys.path.insert(0, str(ROOT))

from utils.logger import logger


def handler(event, context):
    """Cron: every Monday 09:00 UTC — send weekly snapshots to tenant admins."""
    logger.info("weekly_snapshot start", {"event": event})
    # Ensure SES env defaults for scheduled runs
    os.environ.setdefault("SES_ENABLED", "true")
    from modules.agent.src.weekly_snapshot import send_weekly_snapshots

    result = send_weekly_snapshots()
    logger.info(
        "weekly_snapshot done",
        {"tenantCount": len(result.get("tenants") or [])},
    )
    return {
        "statusCode": 200,
        "body": json.dumps(result, default=str),
    }
