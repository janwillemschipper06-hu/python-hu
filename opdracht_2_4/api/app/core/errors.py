"""Application-wide error-handling middleware.

Starlette runs its base ``Exception`` handler in the outermost
``ServerErrorMiddleware`` — *outside* ``CORSMiddleware`` — so a 500 produced
there never flows back through CORS, and the browser reports a misleading
"blocked by CORS policy" error instead of the real 500.
:class:`CatchAllErrorsMiddleware` is registered *before* ``CORSMiddleware`` (so
CORS wraps it), catches the exception here, and returns the JSON 500 through the
CORS layer, which then applies the ``Access-Control-*`` headers.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi.responses import JSONResponse

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)


class CatchAllErrorsMiddleware:
    """Convert unhandled exceptions into a JSON 500 *inside* the CORS layer.

    Mirrors ``ServerErrorMiddleware`` by re-raising if the response has already
    started streaming, so a half-sent response is not corrupted.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Wrap the downstream ASGI ``app`` this middleware guards."""
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Pass the request through, turning any unhandled error into a JSON 500."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def send_wrapper(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:  # deliberate catch-all: convert any error to a JSON 500.
            logger.exception(
                "Unhandled exception processing %s %s",
                scope.get("method", "?"),
                scope.get("path", "?"),
            )
            if response_started:
                raise
            response = JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
            )
            await response(scope, receive, send)
