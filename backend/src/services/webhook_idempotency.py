"""Webhook idempotency service — dedupe LINE webhook event redelivery (N-6)."""

from __future__ import annotations

import os
import time
from typing import Any

import boto3
from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError

logger = Logger()

# How long records are retained before DynamoDB TTL cleanup (seconds).
_TTL_SECONDS = 24 * 60 * 60  # 24 hours

# An in-progress claim older than this is considered stale and may be re-acquired
# (the previous attempt likely crashed/timed out). Must exceed the webhook
# Lambda timeout so a slow-but-alive run is not double-processed.
_STALE_SECONDS = 180  # 3 minutes (> Lambda Timeout 120s)

_STATUS_IN_PROGRESS = "in_progress"
_STATUS_PROCESSED = "processed"


class WebhookIdempotencyService:
    """Makes LINE webhook handling idempotent without losing events on failure.

    LINE delivers webhooks at-least-once and may redeliver events
    (``deliveryContext.isRedelivery``) — including when the previous attempt
    failed. A naive "mark processed before handling" guard prevents double
    processing but silently drops events whose handling crashed/failed.

    This service uses a two-phase claim:

    1. ``try_acquire`` writes an ``in_progress`` claim (conditional put). The
       first caller wins; a concurrent/redelivered caller is rejected. A claim
       left ``in_progress`` past ``_STALE_SECONDS`` (previous run crashed) can be
       re-acquired.
    2. On success the caller calls ``mark_processed`` → the record flips to
       ``processed`` and future redeliveries are skipped for ``_TTL_SECONDS``.
    3. On failure the caller calls ``release`` → the ``in_progress`` claim is
       deleted so LINE's redelivery can retry immediately.
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
        """Claim an event_id for processing (in-progress).

        Args:
            event_id: LINE ``webhookEventId``. Falsy values are treated as
                "cannot dedupe" and are allowed through.
            now: Optional unix timestamp override (for tests).

        Returns:
            True  — claim acquired (first time, or previous claim was stale):
                    the caller should process and then call ``mark_processed``
                    on success / ``release`` on failure.
            False — already processed, or another attempt is in flight:
                    the caller should skip.

        Fails open (returns True) on unexpected errors so a tracking-table
        outage does not silently drop real user events.
        """
        if not event_id:
            # No id to dedupe on — process it (cannot guarantee idempotency).
            return True
        ts = int(now if now is not None else time.time())
        stale_before = ts - _STALE_SECONDS
        try:
            self.table.put_item(
                Item={
                    "webhook_event_id": event_id,
                    "status": _STATUS_IN_PROGRESS,
                    "claimed_at": ts,
                    "expires_at": ts + _TTL_SECONDS,
                },
                # Acquire if: never seen, OR a stale in-progress claim (previous
                # attempt crashed). A `processed` record or a fresh in-progress
                # claim blocks acquisition.
                ConditionExpression=(
                    "attribute_not_exists(webhook_event_id) "
                    "OR (#s = :inprog AND claimed_at < :stale)"
                ),
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":inprog": _STATUS_IN_PROGRESS,
                    ":stale": stale_before,
                },
            )
            return True
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                logger.info(
                    "Duplicate or in-flight webhook event ignored",
                    extra={"event_id": event_id},
                )
                return False
            logger.warning(
                "Idempotency check failed; processing anyway (fail-open)",
                extra={"event_id": event_id, "error": str(e)},
            )
            return True

    def mark_processed(self, event_id: str | None, now: float | None = None) -> None:
        """Flip a claim to ``processed`` after successful handling (best-effort)."""
        if not event_id:
            return
        ts = int(now if now is not None else time.time())
        try:
            self.table.update_item(
                Key={"webhook_event_id": event_id},
                UpdateExpression="SET #s = :done, expires_at = :exp",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":done": _STATUS_PROCESSED,
                    ":exp": ts + _TTL_SECONDS,
                },
            )
        except ClientError as e:
            # Best-effort: if this fails the claim stays in-progress and becomes
            # re-acquirable after _STALE_SECONDS, which is the safe direction.
            logger.warning(
                "Failed to mark webhook event processed (best-effort)",
                extra={"event_id": event_id, "error": str(e)},
            )

    def release(self, event_id: str | None) -> None:
        """Delete an in-progress claim after a failure so redelivery can retry.

        Conditional on the record still being ``in_progress`` so we never delete
        a claim another worker has already marked ``processed``.
        """
        if not event_id:
            return
        try:
            self.table.delete_item(
                Key={"webhook_event_id": event_id},
                ConditionExpression="#s = :inprog",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":inprog": _STATUS_IN_PROGRESS},
            )
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                # Already processed (or gone) — nothing to release.
                return
            logger.warning(
                "Failed to release webhook claim (best-effort)",
                extra={"event_id": event_id, "error": str(e)},
            )
