from pathlib import Path

from starlette.requests import Request
from starlette.responses import FileResponse, Response

_DIST_DIR = Path(__file__).parent / "static" / "dist"
_INDEX_HTML = _DIST_DIR / "index.html"


async def serve_spa(request: Request) -> Response:
    """Serve the SPA index.html for the root route."""
    return FileResponse(_INDEX_HTML)


async def serve_static(request: Request) -> Response:
    """Serve static files or fall back to index.html for SPA routing."""
    path = request.path_params.get("path", "")
    file_path = _DIST_DIR / path

    if path and file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    return FileResponse(_INDEX_HTML)
