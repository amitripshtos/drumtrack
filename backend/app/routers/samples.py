import json
import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from app.config import settings

router = APIRouter(prefix="/api/samples", tags=["samples"])

# Only allow simple alphanumeric names with hyphens/underscores
_SAFE_NAME = re.compile(r"^[a-zA-Z0-9_-]+$")
_SAFE_FILE = re.compile(r"^[a-zA-Z0-9_-]+\.wav$")


def _validate_name(value: str, label: str) -> None:
    if not _SAFE_NAME.match(value):
        raise HTTPException(status_code=400, detail=f"Invalid {label}")


def _resolve_kit_dir(set_name: str):
    """Return the kit directory path, checking static first then storage."""
    static = settings.static_samples_dir / set_name
    if static.is_dir():
        return static
    storage = settings.samples_dir / set_name
    if storage.is_dir():
        return storage
    return None


def _list_kit_names() -> list[str]:
    """Merge kit names from static and storage directories, only including kits with a valid kit.json."""
    names: set[str] = set()
    for base in (settings.static_samples_dir, settings.samples_dir):
        if base.exists():
            for d in base.iterdir():
                if d.is_dir() and (d / "kit.json").is_file():
                    names.add(d.name)
    return sorted(names)


@router.get("/")
async def list_sample_sets() -> list[str]:
    """List available sample sets."""
    return _list_kit_names()


@router.get("/{set_name}")
async def get_kit_manifest(set_name: str) -> JSONResponse:
    """Return the kit.json manifest for a sample set."""
    _validate_name(set_name, "set name")

    kit_dir = _resolve_kit_dir(set_name)
    if kit_dir is None:
        raise HTTPException(status_code=404, detail="Sample set not found")

    manifest_path = kit_dir / "kit.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Kit manifest not found")

    with open(manifest_path) as f:
        data = json.load(f)

    return JSONResponse(content=data)


@router.get("/{set_name}/{file_name}")
async def get_sample(set_name: str, file_name: str) -> FileResponse:
    """Serve an individual sample WAV file."""
    _validate_name(set_name, "set name")
    if not _SAFE_FILE.match(file_name):
        raise HTTPException(status_code=400, detail="Invalid file name")

    kit_dir = _resolve_kit_dir(set_name)
    if kit_dir is None:
        raise HTTPException(status_code=404, detail="Sample set not found")

    sample_path = kit_dir / file_name
    if not sample_path.exists():
        raise HTTPException(status_code=404, detail="Sample not found")

    return FileResponse(sample_path, media_type="audio/wav")
