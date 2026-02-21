"""LINE Messaging API service."""

import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import boto3
import httpx
from botocore.exceptions import ClientError

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler.exceptions import UnauthorizedError

from .user_service import UserService

logger = Logger()


class LineServiceError(Exception):
    """Base exception for LINE service errors."""

    pass


class SignatureVerificationError(LineServiceError):
    """Raised when signature verification fails."""

    pass


class LineApiError(LineServiceError):
    """Raised when LINE API call fails."""

    pass


class UserNotLinkedError(LineServiceError):
    """Raised when LINE user is not linked to system user."""

    pass


@dataclass
class LineEvent:
    """Parsed LINE webhook event."""

    event_type: str
    source_user_id: str
    reply_token: Optional[str]
    postback_data: Optional[str]
    timestamp: int


def verify_signature(body: str, signature: str | None, channel_secret: str) -> bool:
    """Verify LINE webhook signature using timing-safe comparison.

    Implements timing-safe signature verification to prevent timing attacks.
    The hmac.compare_digest function is always called, regardless of whether
    the signature is present, to ensure constant-time comparison.

    Args:
        body: Request body as string.
        signature: X-Line-Signature header value (None or str).
        channel_secret: LINE Channel Secret.

    Returns:
        True if signature is valid, False otherwise.
    """
    # Normalize None to empty string for timing-safe comparison
    if signature is None:
        signature = ""

    # Calculate expected signature
    hash_value = hmac.new(
        channel_secret.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    expected = base64.b64encode(hash_value).decode("utf-8")

    # Timing-safe comparison (constant-time)
    return hmac.compare_digest(expected, signature)


class LineService:
    """Service for LINE Messaging API operations."""

    API_BASE_URL = "https://api.line.me/v2/bot"

    def __init__(
        self,
        channel_access_token: Optional[str] = None,
        channel_secret: Optional[str] = None,
        user_service: Optional[UserService] = None,
    ):
        """Initialize LineService.

        Args:
            channel_access_token: LINE Channel Access Token.
            channel_secret: LINE Channel Secret.
            user_service: UserService for user lookup.
        """
        self.channel_access_token = channel_access_token
        self.channel_secret = channel_secret
        self.user_service = user_service or UserService()
        self.channel_id = os.environ.get("LINE_CHANNEL_ID")

        # Load from Secrets Manager if not provided
        if not self.channel_access_token or not self.channel_secret:
            self._load_credentials_from_secrets_manager()

    def _load_credentials_from_secrets_manager(self) -> None:
        """Load LINE credentials from AWS Secrets Manager."""
        secret_arn = os.environ.get("LINE_CHANNEL_SECRET_ARN")
        if not secret_arn:
            return

        try:
            client = boto3.client("secretsmanager")
            response = client.get_secret_value(SecretId=secret_arn)
            secret = json.loads(response["SecretString"])
            self.channel_access_token = secret.get("channel_access_token")
            self.channel_secret = secret.get("channel_secret")
        except ClientError:
            pass

    def verify_request(self, body: str, signature: str) -> bool:
        """Verify LINE webhook request signature.

        Args:
            body: Request body as string.
            signature: X-Line-Signature header value.

        Returns:
            True if signature is valid.

        Raises:
            SignatureVerificationError: If channel secret not configured.
        """
        if not self.channel_secret:
            raise SignatureVerificationError("Channel secret not configured")

        return verify_signature(body, signature, self.channel_secret)

    def parse_events(self, body: str) -> List[LineEvent]:
        """Parse LINE webhook events from request body.

        Args:
            body: JSON request body string.

        Returns:
            List of parsed LineEvent objects.
        """
        try:
            data = json.loads(body)
            events = []

            for event_data in data.get("events", []):
                event_type = event_data.get("type", "")
                source = event_data.get("source", {})
                source_user_id = source.get("userId", "")

                postback_data = None
                if event_type == "postback":
                    postback = event_data.get("postback", {})
                    postback_data = postback.get("data", "")

                events.append(
                    LineEvent(
                        event_type=event_type,
                        source_user_id=source_user_id,
                        reply_token=event_data.get("replyToken"),
                        postback_data=postback_data,
                        timestamp=event_data.get("timestamp", 0),
                    )
                )

            return events
        except json.JSONDecodeError:
            return []

    def get_user_id_from_line(self, line_user_id: str) -> Optional[str]:
        """Get system user ID from LINE user ID.

        Args:
            line_user_id: LINE user ID.

        Returns:
            System user ID if linked, None otherwise.
        """
        user = self.user_service.get_user_by_line_id(line_user_id)
        return user.user_id if user else None

    def verify_id_token(self, id_token: str) -> str:
        """Verify LIFF ID token via LINE API and return line_user_id.

        Calls https://api.line.me/oauth2/v2.1/verify with the LIFF ID token
        and LINE_CHANNEL_ID, then extracts the 'sub' claim as line_user_id.

        Args:
            id_token: LIFF SDK getIDToken() result.

        Returns:
            Verified line_user_id (the 'sub' claim from LINE API response).

        Raises:
            LineApiError: If LINE_CHANNEL_ID is not configured or network error occurs.
            UnauthorizedError: If ID token verification fails or 'sub' claim is missing.
        """
        if not self.channel_id:
            raise LineApiError("LINE_CHANNEL_ID not configured")

        try:
            response = httpx.post(
                "https://api.line.me/oauth2/v2.1/verify",
                data={
                    "id_token": id_token,
                    "client_id": self.channel_id,
                },
                timeout=10,
            )
        except httpx.RequestError as e:
            logger.error(f"ID token verification request failed: {e}")
            raise LineApiError(f"Failed to verify ID token: {e}") from e

        if response.status_code != 200:
            logger.warning(f"LINE ID token verification failed: status={response.status_code}")
            raise UnauthorizedError("LINE ID token verification failed")

        data = response.json()
        line_user_id = data.get("sub")
        if not line_user_id:
            logger.warning("LINE API response missing 'sub' claim")
            raise UnauthorizedError("Invalid ID token format")

        logger.info("LINE ID token verified successfully")
        return line_user_id

    def reply_message(
        self,
        reply_token: str,
        messages: List[Dict[str, Any]],
    ) -> bool:
        """Send reply message using reply token.

        Args:
            reply_token: Reply token from webhook event.
            messages: List of message objects to send.

        Returns:
            True if successful.

        Raises:
            LineApiError: If API call fails.
        """
        if not self.channel_access_token:
            raise LineApiError("Channel access token not configured")

        url = f"{self.API_BASE_URL}/message/reply"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.channel_access_token}",
        }
        payload = {
            "replyToken": reply_token,
            "messages": messages,
        }

        try:
            response = httpx.post(url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            return True
        except httpx.RequestError as e:
            raise LineApiError(f"Failed to send reply: {e}") from e

    def push_message(
        self,
        to: str,
        messages: List[Dict[str, Any]],
    ) -> bool:
        """Send push message to user.

        Args:
            to: LINE user ID to send to.
            messages: List of message objects to send.

        Returns:
            True if successful.

        Raises:
            LineApiError: If API call fails.
        """
        if not self.channel_access_token:
            raise LineApiError("Channel access token not configured")

        url = f"{self.API_BASE_URL}/message/push"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.channel_access_token}",
        }
        payload = {
            "to": to,
            "messages": messages,
        }

        try:
            response = httpx.post(url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            return True
        except httpx.RequestError as e:
            raise LineApiError(f"Failed to send push: {e}") from e
