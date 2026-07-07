"""
Clerk JWT Authentication middleware for FastAPI.
Verifies Bearer tokens using Clerk's JWKS endpoint (RS256).
Automatically registers new users in MongoDB on first login.
"""

import logging
import time
from typing import Optional

import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import asyncio

from config import settings
from database.mongo import get_db
from services.email_service import send_welcome_email

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

_jwks_client: Optional[PyJWKClient] = None


def _get_jwks_client() -> PyJWKClient:
    """Lazy-init the JWKS client (caches keys automatically)."""
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(settings.CLERK_JWKS_URL, cache_keys=True)
    return _jwks_client


def decode_clerk_jwt(token: str) -> dict:
    """
    Decode and verify a Clerk-issued JWT using RS256.

    Returns the full payload dict with at minimum:
        - sub (user_id)
        - email (if available in session claims)
        - first_name, last_name (if configured in Clerk template)
    """
    try:
        jwks = _get_jwks_client()
        signing_key = jwks.get_signing_key_from_jwt(token)

        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=settings.CLERK_ISSUER,
            options={"verify_aud": False},
            leeway=60,  # Cho phép sai số đồng hồ 60 giây giữa Client và Server
        )
        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token đã hết hạn. Vui lòng đăng nhập lại.")
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid Clerk JWT: {e}")
        raise HTTPException(status_code=401, detail="Token không hợp lệ.")


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """
    FastAPI dependency: extract + verify the Clerk JWT from Authorization header.

    Returns a dict with:
        - user_id: str
        - email: str
        - first_name: str | None
        - is_new_user: bool  (True if this is the first time we see this user)
        - health_profile: dict | None
    """
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Yêu cầu đăng nhập để sử dụng tính năng này.",
        )

    payload = decode_clerk_jwt(credentials.credentials)

    user_id = payload.get("sub")
    email = payload.get("email", "")
    first_name = payload.get("first_name") or payload.get("given_name") or ""

    if not user_id:
        raise HTTPException(status_code=401, detail="Token thiếu thông tin người dùng (sub).")

    db = get_db()
    existing_user = await db["users"].find_one({"_id": user_id})

    is_new_user = False
    health_profile = None

    if existing_user is None:
        is_new_user = True
        now = time.time()
        new_user_doc = {
            "_id": user_id,
            "email": email,
            "first_name": first_name,
            "health_profile": {
                "chronic_diseases": [],
                "allergies": [],
                "current_medications": [],
                "age": None,
                "gender": "",
                "height": None,
                "weight": None,
            },
            "created_at": now,
            "updated_at": now,
        }
        await db["users"].insert_one(new_user_doc)
        health_profile = new_user_doc["health_profile"]
        logger.info(f"🆕 New user registered: {email} (ID: {user_id})")

        # Đẩy thẳng vào Event Loop độc lập để không bị huỷ nếu Request bị lỗi 500
        asyncio.create_task(
            asyncio.to_thread(send_welcome_email, email=email, first_name=first_name)
        )
        logger.info(f"📧 Async welcome email task dispatched for {email}")

    else:
        health_profile = existing_user.get("health_profile")
        # ── BAN CHECK: Chặn user bị cấm từ vòng ngoài ──
        if existing_user.get("is_banned", False):
            raise HTTPException(
                status_code=403,
                detail="Tài khoản của bạn đã bị khóa do vi phạm tiêu chuẩn cộng đồng. "
                       "Vui lòng liên hệ quản trị viên nếu bạn cho rằng đây là nhầm lẫn.",
            )

        # ── CLERK USER NAME DESYNC SYNC: Đồng bộ first_name và email từ Clerk ──
        db_email = existing_user.get("email", "")
        db_first_name = existing_user.get("first_name", "")
        
        update_fields = {}
        if email and email != db_email:
            update_fields["email"] = email
        if first_name and first_name != db_first_name:
            update_fields["first_name"] = first_name

        if update_fields:
            update_fields["updated_at"] = time.time()
            await db["users"].update_one(
                {"_id": user_id},
                {"$set": update_fields}
            )
            logger.info(f"🔄 Synced updated Clerk profile info for user_id={user_id}: {update_fields}")

    return {
        "user_id": user_id,
        "email": email,
        "first_name": first_name,
        "is_new_user": is_new_user,
        "health_profile": health_profile,
    }


async def get_current_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """
    FastAPI dependency: chỉ cho phép tài khoản có role=admin từ Clerk publicMetadata.

    Clerk publicMetadata cần được set thủ công qua Clerk Dashboard:
        { "role": "admin" }

    Raise 403 nếu không phải admin, 401 nếu thiếu/hết hạn token.
    """
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Yêu cầu đăng nhập để truy cập trang quản trị.",
        )

    payload = decode_clerk_jwt(credentials.credentials)

    public_metadata = payload.get("public_metadata") or payload.get("publicMetadata") or {}
    role = public_metadata.get("role", "")

    user_id = payload.get("sub", "")

    # Only check Clerk JWT metadata as requested
    if role == "admin":
        return {"user_id": user_id, "role": "admin"}

    raise HTTPException(
        status_code=403,
        detail="Truy cập bị từ chối. Token không có thông tin role='admin' từ Clerk.",
    )
