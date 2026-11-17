"""The shared folder (SHARED_DIR): ML writes blurred images there, the API serves them.

<SHARED_DIR>/images/<image_id>.jpg  ->  GET {MEDIA_URL}/images/<image_id>.jpg
"""

from pathlib import Path

from app.core.config import settings

MEDIA_MOUNT = (
    "/media"  # where main.py serves the folder; MEDIA_URL must end with this path
)
IMAGES_SUBDIR = "images"


def shared_dir() -> Path:
    return Path(settings.SHARED_DIR).resolve()


def images_dir() -> Path:
    return shared_dir() / IMAGES_SUBDIR


def shared_path(relative: str) -> Path:
    """Absolute path of a file in the shared folder (paths come from ML, so keep them inside it)."""
    path = (shared_dir() / relative).resolve()
    if not path.is_relative_to(shared_dir()):
        raise ValueError(f"path outside the shared folder: {relative}")
    return path


def media_url(relative: str) -> str:
    """Public URL of a shared-folder file, e.g. 'images/x.jpg' -> '/media/images/x.jpg'."""
    return f"{settings.MEDIA_URL.rstrip('/')}/{relative.lstrip('/')}"
