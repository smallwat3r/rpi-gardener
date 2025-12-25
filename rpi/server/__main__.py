"""Web server entrypoint.

Runs the Starlette web application using uvicorn. For production,
use uvicorn directly with appropriate workers and socket options:

    uvicorn rpi.server:app --uds /tmp/uvicorn.sock --workers 3

Usage: python -m rpi.server
"""
import uvicorn


def main() -> None:
    """Run the web server for local development."""
    uvicorn.run(
        "rpi.server:app",
        host="0.0.0.0",
        port=5000,
        reload=True,
    )


if __name__ == "__main__":
    main()
