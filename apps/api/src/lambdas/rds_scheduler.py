"""
RDS Scheduler Lambda

Scheduled job to start/stop RDS instances for cost savings.
Triggered by EventBridge scheduled rules.

Environment Variables:
  - DB_INSTANCE_IDENTIFIER: The RDS instance identifier to control
"""
from __future__ import annotations

import json
import os
from typing import Any

import boto3

rds_client = boto3.client("rds")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    db_instance_identifier = event.get("dbInstanceIdentifier") or os.environ.get(
        "DB_INSTANCE_IDENTIFIER"
    )

    if not db_instance_identifier:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "DB_INSTANCE_IDENTIFIER is required"}),
        }

    action = event.get("action")
    print(f"{(action or '').upper()} action requested for RDS: {db_instance_identifier}")

    try:
        describe = rds_client.describe_db_instances(
            DBInstanceIdentifier=db_instance_identifier
        )
        instances = describe.get("DBInstances") or []
        if not instances:
            raise RuntimeError(f"RDS instance not found: {db_instance_identifier}")

        current_status = instances[0].get("DBInstanceStatus") or "unknown"
        print(f"Current instance status: {current_status}")

        if action == "start":
            return _handle_start(db_instance_identifier, current_status)
        if action == "stop":
            return _handle_stop(db_instance_identifier, current_status)

        return {
            "statusCode": 400,
            "body": json.dumps(
                {"error": f"Invalid action: {action}. Must be 'start' or 'stop'"}
            ),
        }
    except Exception as exc:  # noqa: BLE001 — surface to CloudWatch
        print(f"Error {action}ing RDS instance: {exc}")
        return {
            "statusCode": 500,
            "body": json.dumps(
                {"error": f"Failed to {action} RDS instance", "details": str(exc)}
            ),
        }


def _handle_start(db_instance_identifier: str, current_status: str) -> dict[str, Any]:
    if current_status == "available":
        return {
            "statusCode": 200,
            "body": json.dumps(
                {"message": "Instance is already running", "status": current_status}
            ),
        }

    if current_status != "stopped":
        return {
            "statusCode": 409,
            "body": json.dumps(
                {
                    "message": f"Instance is in {current_status} state, cannot start",
                    "status": current_status,
                }
            ),
        }

    rds_client.start_db_instance(DBInstanceIdentifier=db_instance_identifier)
    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": "RDS instance is starting",
                "dbInstanceIdentifier": db_instance_identifier,
                "previousStatus": current_status,
            }
        ),
    }


def _handle_stop(db_instance_identifier: str, current_status: str) -> dict[str, Any]:
    if current_status == "stopped":
        return {
            "statusCode": 200,
            "body": json.dumps(
                {"message": "Instance is already stopped", "status": current_status}
            ),
        }

    if current_status != "available":
        return {
            "statusCode": 409,
            "body": json.dumps(
                {
                    "message": f"Instance is in {current_status} state, cannot stop",
                    "status": current_status,
                }
            ),
        }

    rds_client.stop_db_instance(DBInstanceIdentifier=db_instance_identifier)
    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": "RDS instance is stopping",
                "dbInstanceIdentifier": db_instance_identifier,
                "previousStatus": current_status,
            }
        ),
    }
