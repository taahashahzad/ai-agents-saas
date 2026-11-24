"""Reject obviously oversized uploads from the Content-Length header, before the body is parsed
(FastAPI parses multipart bodies before running dependencies). The exact size is enforced again
while reading the file. Chunked uploads without Content-Length are only caught by that second
check, so also set a body-size limit on your reverse proxy / load balancer in production."""
import re

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

_UPLOAD_PATH = re.compile(r"^/api/v1/businesses/[^/]+/documents/?$")
_MULTIPART_OVERHEAD = 1024 * 1024  # headers/boundaries around the file


class UploadSizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_bytes: int):
        super().__init__(app)
        self._limit = max_bytes + _MULTIPART_OVERHEAD
        self._max_mb = max_bytes / (1024 * 1024)

    async def dispatch(self, request, call_next):
        if request.method == "POST" and _UPLOAD_PATH.match(request.url.path):
            length = request.headers.get("content-length")
            if length and length.isdigit() and int(length) > self._limit:
                return JSONResponse(status_code=413, content={"error": {
                    "code": "file_too_large",
                    "message": f"The file exceeds the maximum size of {self._max_mb:g} MB."}})
        return await call_next(request)
