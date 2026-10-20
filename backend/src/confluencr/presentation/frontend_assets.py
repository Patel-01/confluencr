from pathlib import Path


def frontend_dist_path() -> Path:
    """Locate the built frontend from either the repository or backend directory."""
    candidates = (
        Path.cwd() / "frontend" / "dist",
        Path(__file__).resolve().parents[4] / "frontend" / "dist",
    )
    return next((path for path in candidates if path.is_dir()), candidates[0])
