"""Local development server command."""

from __future__ import annotations


def main() -> None:
    import uvicorn

    uvicorn.run(
        "linkedin_profile_api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
