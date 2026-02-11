import asyncio
import logging
from pathlib import Path

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

LALAL_BASE = "https://www.lalal.ai/api"


async def upload_file(file_path: Path) -> str:
    """Upload audio file to LALAL.AI, return file_id."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        with open(file_path, "rb") as f:
            resp = await client.post(
                f"{LALAL_BASE}/upload/",
                headers={"Authorization": f"license {settings.lalal_api_key}"},
                files={"file": (file_path.name, f, "audio/mpeg")},
            )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "error":
            raise RuntimeError(f"LALAL upload error: {data}")
        return data["id"]


async def start_split(file_id: str) -> None:
    """Request stem separation for drums."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{LALAL_BASE}/split/",
            headers={"Authorization": f"license {settings.lalal_api_key}"},
            json={
                "id": file_id,
                "filter": 2,  # drums filter
                "stem": "drums",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "error":
            raise RuntimeError(f"LALAL split error: {data}")


async def poll_until_done(file_id: str, max_wait: int = 600) -> dict:
    """Poll LALAL.AI until separation is complete. Returns task result."""
    elapsed = 0
    interval = 5
    async with httpx.AsyncClient(timeout=30.0) as client:
        while elapsed < max_wait:
            resp = await client.post(
                f"{LALAL_BASE}/check/",
                headers={"Authorization": f"license {settings.lalal_api_key}"},
                json={"id": file_id},
            )
            resp.raise_for_status()
            data = resp.json()

            task = data.get("result", {}).get(file_id, {}).get("task", {})
            state = task.get("state")

            if state == "success":
                return data["result"][file_id]
            elif state == "error":
                raise RuntimeError(f"LALAL separation failed: {task}")

            logger.info(f"LALAL status: {state}, waiting {interval}s...")
            await asyncio.sleep(interval)
            elapsed += interval

    raise TimeoutError("LALAL.AI separation timed out")


async def download_stems(result: dict, drum_path: Path, other_path: Path) -> None:
    """Download drum and other stems from LALAL.AI result."""
    stem_url = result["split"]["stem_track"]
    back_url = result["split"]["back_track"]

    async with httpx.AsyncClient(timeout=120.0) as client:
        # Download drum stem
        resp = await client.get(stem_url)
        resp.raise_for_status()
        drum_path.write_bytes(resp.content)

        # Download backing track
        resp = await client.get(back_url)
        resp.raise_for_status()
        other_path.write_bytes(resp.content)
