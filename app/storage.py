# File saving logic (saves to data/uploads)
import shutil
import uuid
from pathlib import Path
from app.config import settings

class Storage:
    """Local-disk storage logic."""
    def __init__(self, base: Path | None = None):
        self.base = base or (settings.data_path / "uploads")
        self.base.mkdir(parents=True, exist_ok=True)

    def save(self, src_filename: str, fileobj) -> tuple[str, int]:
        ext = Path(src_filename).suffix.lower()
        new_name = f"{uuid.uuid4().hex}{ext}"
        dest = self.base / new_name
        with open(dest, "wb") as out:
            shutil.copyfileobj(fileobj, out)
        return str(dest), dest.stat().st_size

    def open(self, path: str):
        return open(path, "rb")

storage = Storage()