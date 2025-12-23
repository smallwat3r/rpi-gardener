from pathlib import Path

from flask import Blueprint, send_from_directory

spa = Blueprint("spa", __name__)

_DIST_DIR = Path(__file__).parent / "static" / "dist"


@spa.get("/")
@spa.get("/<path:path>")
def serve_spa(path: str = "") -> tuple:
    """Serve the SPA for all non-API routes."""
    if path and (_DIST_DIR / path).exists():
        return send_from_directory(_DIST_DIR, path)
    return send_from_directory(_DIST_DIR, "index.html")
