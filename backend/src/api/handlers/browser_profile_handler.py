"""Browser profile API route handler."""

import json
from typing import Optional

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import Response, content_types
from aws_lambda_powertools.event_handler.api_gateway import Router
from pydantic import BaseModel, Field, ValidationError

from api.shared import get_user_id_from_context, make_validation_error_response
from services.browser_profile_service import (
    BrowserProfileService,
    BrowserProfileError,
)


class BrowserProfileCreateRequest(BaseModel):
    """Request model for creating a browser profile."""

    name: str = Field(..., min_length=1, max_length=100, description="Profile name")


class BrowserProfileUpdateRequest(BaseModel):
    """Request model for updating a browser profile."""

    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Profile name")

logger = Logger()
tracer = Tracer()
router = Router()

profile_service = BrowserProfileService()


@router.get("/browser-profiles")
@tracer.capture_method
def list_profiles():
    """List browser profiles for the current user."""
    user_id = get_user_id_from_context(router)
    logger.info("Listing browser profiles", extra={"user_id": user_id})

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
        logger.error("Error listing profiles", extra={"error": str(e)})
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
    logger.info("Creating browser profile", extra={"user_id": user_id})

    try:
        body = router.current_event.json_body
        request = BrowserProfileCreateRequest(**body)
    except ValidationError as e:
        logger.warning("Validation error", extra={"error": str(e)})
        return make_validation_error_response(e)
    except json.JSONDecodeError:
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "Invalid JSON body"}),
        )

    try:
        profile = profile_service.create_profile(user_id=user_id, name=request.name)

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
        logger.error("Error creating profile", extra={"error": str(e)})
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
    logger.info("Deleting browser profile", extra={"profile_id": profile_id, "user_id": user_id})

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
        logger.error("Error deleting profile", extra={"profile_id": profile_id, "error": str(e)})
        return Response(
            status_code=500,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "Failed to delete profile"}),
        )
