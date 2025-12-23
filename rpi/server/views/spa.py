from pathlib import Path

from flask import Blueprint, send_from_directory

spa = Blueprint("spa", __name__)

DIST_DIR = Path(__file__).parent.parent / "static" / "dist"


@spa.get("/")
@spa.get("/<path:path>")
def serve_spa(path: str = "") -> tuple:
    """Serve the SPA for all non-API routes."""
    if path and (DIST_DIR / path).exists():
        return send_from_directory(DIST_DIR, path)
    return send_from_directory(DIST_DIR, "index.html")
