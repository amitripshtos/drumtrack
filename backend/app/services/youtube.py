import subprocess
from pathlib import Path


def get_video_title(url: str) -> str | None:
    """Extract video title from a YouTube URL using yt-dlp."""
    try:
        result = subprocess.run(
            ["yt-dlp", "--get-title", "--no-warnings", "--no-playlist", url],
            capture_output=True,
            text=True,
            timeout=30,
            stdin=subprocess.DEVNULL,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return None


def download_youtube(url: str, output_path: Path) -> Path:
    """Download audio from YouTube URL as MP3 using yt-dlp."""
    # Give yt-dlp the path WITHOUT extension — it adds .mp3 via --audio-format
    stem_path = output_path.with_suffix("")
    cmd = [
        "yt-dlp",
        "-x",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "--no-playlist",
        "--no-warnings",
        "-o", str(stem_path) + ".%(ext)s",
        url,
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=300,
        stdin=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {result.stderr}")
    if output_path.exists():
        return output_path
    raise FileNotFoundError(f"Downloaded file not found at {output_path}")
