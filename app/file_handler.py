from __future__ import annotations

import base64
import io
import json
import zipfile

SUPPORTED_MIME_TYPES: dict[str, str] = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "svg": "image/svg+xml",
}

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


def process_uploaded_file(content: bytes, filename: str) -> dict:
    """Process an uploaded file and return a mode descriptor.

    Returns one of:
        {"mode": "image",      "base64": str, "mime_type": str}
        {"mode": "figma_json", "data": dict,  "file_id": str}

    Raises:
        ValueError: unsupported format or unparseable .fig binary.
    """
    if len(content) > MAX_FILE_SIZE:
        mb = MAX_FILE_SIZE // 1024 // 1024
        raise ValueError(f"Файл слишком большой (максимум {mb} МБ).")

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext in SUPPORTED_MIME_TYPES:
        b64 = base64.b64encode(content).decode()
        return {"mode": "image", "base64": b64, "mime_type": SUPPORTED_MIME_TYPES[ext]}

    if ext == "fig":
        return _process_fig(content, filename)

    raise ValueError(
        f"Неподдерживаемый формат файла «{filename}». "
        "Поддерживаются: PNG, JPG, SVG, .fig."
    )


def _process_fig(content: bytes, filename: str) -> dict:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            json_candidates = [n for n in zf.namelist() if n.endswith(".json")]
            if not json_candidates:
                raise ValueError(
                    "Файл .fig не содержит JSON-данных. "
                    "Загрузите файл в Figma и используйте ссылку вместо файла."
                )
            data = json.loads(zf.read(json_candidates[0]))
            file_id = filename.rsplit(".", 1)[0]
            return {"mode": "figma_json", "data": data, "file_id": file_id}
    except zipfile.BadZipFile:
        raise ValueError(
            "Файл .fig имеет бинарный формат, который не поддерживается напрямую. "
            "Загрузите файл в Figma и используйте ссылку на него вместо файла."
        )
