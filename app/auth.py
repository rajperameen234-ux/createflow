"""Authentication dependency.

Protected routes require a Supabase access token. When Supabase is not
configured the server refuses protected routes explicitly instead of pretending
authentication succeeded.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from fastapi import Header, HTTPException, status

from .cloud import MISSING_CONFIG_MESSAGE, get_cloud

log = logging.getLogger("createflow.auth")

DEV_HEADER = "x-createflow-dev-user"


@dataclass
class Identity:
    id: str
    email: Optional[str] = None
    mode: str = "supabase"


async def require_user(
    authorization: Optional[str] = Header(default=None),
    x_createflow_dev_user: Optional[str] = Header(default=None, alias=DEV_HEADER),
) -> Identity:
    cloud = get_cloud()

    if authorization:
        token = authorization[7:].strip() if authorization.lower().startswith("bearer ") else authorization.strip()
        if not token:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authorization header contained no token.")
        user = cloud.verify_token(token)
        if not user:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "Invalid or expired access token. Sign in again in the app.",
            )
        user_id = user.get("id")
        if not user_id or user_id == "None":
            # Never fall through to an unauthenticated identity: an empty id
            # would turn every ownership filter into a no-op.
            log.error("token verified but no user id was returned; refusing the request")
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "The access token did not resolve to a user. Sign in again in the app.",
            )
        return Identity(id=str(user_id), email=user.get("email"), mode="supabase")

    if x_createflow_dev_user:
        if not cloud.configured:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                f"{MISSING_CONFIG_MESSAGE} Development identity headers are only accepted when "
                "the cloud is configured, so local results are never mistaken for saved work.",
            )
        log.info("accepted development identity header")
        return Identity(id=x_createflow_dev_user.strip()[:80], mode="development")

    if not cloud.configured:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"{MISSING_CONFIG_MESSAGE} Configure Supabase to use projects, downloads and cloud saving.",
        )

    raise HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Missing bearer token. Sign in with Supabase Auth to access projects.",
    )


async def optional_user(
    authorization: Optional[str] = Header(default=None),
    x_createflow_dev_user: Optional[str] = Header(default=None, alias=DEV_HEADER),
) -> Optional[Identity]:
    try:
        return await require_user(authorization, x_createflow_dev_user)
    except HTTPException:
        return None