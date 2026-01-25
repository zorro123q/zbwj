import os
import uuid
from pathlib import Path

from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import File


def _get_ext(filename: str) -> str:
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower().strip()


def save_uploaded_file(file_storage: FileStorage) -> dict:
    """
    Save upload to:
      storage/uploads/<file_id>/original.<ext>
    Insert DB record into files table.
    Return: {file_id, filename, ext, size}
    """
    original_name = file_storage.filename or ""
    safe_name = secure_filename(original_name)

    if not safe_name:
        raise ValueError("invalid filename")

    ext = _get_ext(safe_name)
    allowed = set(current_app.config.get("UPLOAD_ALLOWED_EXTENSIONS", set()))
    if ext not in allowed:
        raise ValueError("only txt/docx are allowed")

    file_id = str(uuid.uuid4())

    rel_storage_path = f"{current_app.config.get('UPLOAD_STORAGE_DIR', 'storage/uploads')}/{file_id}/original.{ext}"
    rel_storage_path = rel_storage_path.replace("\\", "/")  # normalize

    # Resolve absolute path safely (no user-controlled path segments)
    repo_root = Path(current_app.root_path).parent  # .../<repo>/app -> .../<repo>
    abs_path = repo_root / Path(rel_storage_path)

    abs_path.parent.mkdir(parents=True, exist_ok=True)

    # Save file (Flask will enforce MAX_CONTENT_LENGTH=20MB)
    file_storage.save(str(abs_path))

    size = abs_path.stat().st_size
    if size > int(current_app.config.get("MAX_CONTENT_LENGTH", 0) or 0):
        # Just in case server/proxy didn't enforce
        try:
            abs_path.unlink(missing_ok=True)  # py3.8 doesn't have missing_ok; handled below
        except TypeError:
            if abs_path.exists():
                abs_path.unlink()
        raise ValueError("file too large (max 20MB)")

    rec = File(
        id=file_id,
        filename=safe_name,
        ext=ext,
        size=int(size),
        storage_path=rel_storage_path,
    )
    db.session.add(rec)
    db.session.commit()

    return {
        "file_id": file_id,
        "filename": safe_name,
        "ext": ext,
        "size": int(size),
    }
