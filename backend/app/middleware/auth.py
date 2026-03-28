"""Optional bearer token authentication middleware.

Only active when COCO_AUTH_TOKEN is set. When not set, all requests pass through.
This is intentionally simple — CoCo is designed for single-user local use.
For multi-user deployments, put a proper auth proxy in front.
"""
import os
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

AUTH_TOKEN = os.getenv("COCO_AUTH_TOKEN", "")

# Paths that never require auth
PUBLIC_PATHS = {
    "/api/health",
    "/api/edition",
    "/docs",
    "/openapi.json",
    "/redoc",
}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # If no token configured, skip auth entirely
        if not AUTH_TOKEN:
            return await call_next(request)

        path = request.url.path

        # Allow public paths
        if path in PUBLIC_PATHS:
            return await call_next(request)

        # Allow static files
        if not path.startswith("/api/"):
            return await call_next(request)

        # Check Authorization header
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

        token = auth_header[7:]  # Strip "Bearer "
        if token != AUTH_TOKEN:
            raise HTTPException(status_code=401, detail="Invalid authentication token")

        return await call_next(request)
