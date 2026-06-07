"""Webhook idempotency service — dedupe LINE webhook event redelivery (N-6)."""

from __future__ import annotations

import os
import time
from typing import Any

import boto3
from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError

logger = Logger()

# How long processed event IDs are retained before TTL cleanup (seconds).
_TTL_SECONDS = 24 * 60 * 60  # 24 hours


class WebhookIdempotencyService:
    """Tracks processed LINE webhook event IDs to make handling idempotent.

    LINE delivers webhooks at-least-once and may redeliver events
    (``deliveryContext.isRedelivery``). Without a dedupe guard, a redelivered
    postback would re-run side effects such as ``submit_review`` (double
    recording). Each event_id is claimed with a conditional put: the first
    caller wins, redeliveries are rejected.
    """

    def __init__(
        self,
        table_name: str | None = None,
        dynamodb_resource: Any | None = None,
    ) -> None:
        self.table_name = table_name or os.environ.get(
            "PROCESSED_EVENTS_TABLE", "memoru-processed-events-dev"
        )
        if dynamodb_resource:
            self.dynamodb = dynamodb_resource
        else:
            endpoint_url = os.environ.get("DYNAMODB_ENDPOINT_URL") or os.environ.get(
                "AWS_ENDPOINT_URL"
            )
            if endpoint_url:
                self.dynamodb = boto3.resource("dynamodb", endpoint_url=endpoint_url)
            else:
                self.dynamodb = boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(self.table_name)

    def try_acquire(self, event_id: str | None, now: float | None = None) -> bool:
        """Atomically claim an event_id for processing.

        Args:
            event_id: LINE ``webhookEventId``. Falsy values are treated as
                "cannot dedupe" and are allowed through.
            now: Optional unix timestamp override (for tests).

        Returns:
            True  — first time seen (or no id available): caller should process.
            False — already processed: caller should skip (redelivery).

        Fails open (returns True) on unexpected errors so that a tracking-table
        outage does not silently drop real user events.
        """
        if not event_id:
            # No id to dedupe on — process it (cannot guarantee idempotency).
            return True
        ts = now if now is not None else time.time()
        expires_at = int(ts) + _TTL_SECONDS
        try:
            self.table.put_item(
                Item={"webhook_event_id": event_id, "expires_at": expires_at},
                ConditionExpression="attribute_not_exists(webhook_event_id)",
            )
            return True
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                logger.info("Duplicate webhook event ignored", extra={"event_id": event_id})
                return False
            logger.warning(
                "Idempotency check failed; processing anyway (fail-open)",
                extra={"event_id": event_id, "error": str(e)},
            )
            return True
