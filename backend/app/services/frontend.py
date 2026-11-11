"""Serve both compiled SPAs on one origin without swallowing missing API routes."""

from pathlib import Path

from fastapi import HTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import RedirectResponse
from starlette.staticfiles import StaticFiles


class SPAFiles(StaticFiles):
    async def get_response(self, path, scope):
        if any(
            part.startswith(".") and part not in {".", ".."} for part in path.split("/")
        ):
            raise HTTPException(404, "Not found")
        if path.split("/")[0] in {"api", "ws", "docs", "redoc", "openapi.json"}:
            raise HTTPException(404, "Not found")
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as error:
            if (
                error.status_code != 404
                or Path(path).suffix
                or scope["method"] not in {"GET", "HEAD"}
            ):
                raise
            response = await super().get_response("index.html", scope)
        response.headers["Cache-Control"] = (
            "public, max-age=31536000, immutable"
            if path.startswith("assets/") and response.status_code == 200
            else "no-cache"
        )
        return response


def mount_frontends(app, directory):
    root = Path(directory).resolve()
    for name in ("bank", "admin"):
        if not (root / name / "index.html").is_file():
            raise RuntimeError(f"Compiled {name} frontend is missing")

    @app.get("/admin", include_in_schema=False)
    def admin_redirect():
        return RedirectResponse("/admin/", status_code=307)

    app.mount("/admin", SPAFiles(directory=root / "admin", html=True), name="admin-ui")
    app.mount("/", SPAFiles(directory=root / "bank", html=True), name="bank-ui")
