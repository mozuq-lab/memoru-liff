"""Browser profile API route handler."""

import json

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import Response, content_types
from aws_lambda_powertools.event_handler.api_gateway import Router

from api.shared import get_user_id_from_context
from services.browser_profile_service import (
    BrowserProfileService,
    BrowserProfileError,
)

logger = Logger()
tracer = Tracer()
router = Router()

profile_service = BrowserProfileService()


@router.get("/browser-profiles")
@tracer.capture_method
def list_profiles():
    """List browser profiles for the current user."""
    user_id = get_user_id_from_context(router)
    logger.info(f"Listing browser profiles for user_id: {user_id}")

    try:
        profiles = profile_service.list_profiles(user_id)
        return {
            "profiles": [
                {
                    "profile_id": p.profile_id,
                    "name": p.name,
                    "created_at": p.created_at,
                }
                for p in profiles
            ]
        }
    except BrowserProfileError as e:
        logger.error(f"Error listing profiles: {e}")
        return Response(
            status_code=500,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "Failed to list profiles"}),
        )


@router.post("/browser-profiles")
@tracer.capture_method
def create_profile():
    """Create a new browser profile."""
    user_id = get_user_id_from_context(router)
    logger.info(f"Creating browser profile for user_id: {user_id}")

    try:
        body = router.current_event.json_body
        if not isinstance(body, dict):
            return Response(
                status_code=400,
                content_type=content_types.APPLICATION_JSON,
                body=json.dumps({"error": "Request body must be a JSON object"}),
            )

        name = body.get("name", "").strip()
        if not name:
            return Response(
                status_code=400,
                content_type=content_types.APPLICATION_JSON,
                body=json.dumps({"error": "Profile name is required"}),
            )
        if len(name) > 100:
            return Response(
                status_code=400,
                content_type=content_types.APPLICATION_JSON,
                body=json.dumps({"error": "Profile name must be 100 characters or less"}),
            )

        profile = profile_service.create_profile(user_id=user_id, name=name)

        return Response(
            status_code=201,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({
                "profile_id": profile.profile_id,
                "name": profile.name,
                "created_at": profile.created_at,
            }),
        )
    except BrowserProfileError as e:
        logger.error(f"Error creating profile: {e}")
        return Response(
            status_code=500,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "Failed to create profile"}),
        )


@router.delete("/browser-profiles/<profile_id>")
@tracer.capture_method
def delete_profile(profile_id: str):
    """Delete a browser profile."""
    user_id = get_user_id_from_context(router)
    logger.info(f"Deleting browser profile {profile_id} for user_id: {user_id}")

    try:
        deleted = profile_service.delete_profile(user_id, profile_id)

        if not deleted:
            return Response(
                status_code=404,
                content_type=content_types.APPLICATION_JSON,
                body=json.dumps({"error": "Profile not found"}),
            )

        return {"message": "Profile deleted"}
    except BrowserProfileError as e:
        logger.error(f"Error deleting profile: {e}")
        return Response(
            status_code=500,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "Failed to delete profile"}),
        )
