import hashlib
import uuid
from pathlib import Path
from werkzeug.utils import secure_filename


def allowed_file(filename: str, allowed_extensions: set[str]) -> bool:
    """Check if the filename has an allowed extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def is_valid_pdf_header(file_stream) -> bool:
    """Verify the uploaded file starts with the PDF magic bytes (%PDF-)."""
    pos = file_stream.tell()
    header = file_stream.read(5)
    file_stream.seek(pos)
    return header == b"%PDF-"


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA-256 hex digest for duplicate detection."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def generate_stored_filename(original_filename: str) -> str:
    """Generate a unique, filesystem-safe filename preserving the .pdf extension."""
    safe_name = secure_filename(original_filename) or "document.pdf"
    return f"{uuid.uuid4().hex}_{safe_name}"
