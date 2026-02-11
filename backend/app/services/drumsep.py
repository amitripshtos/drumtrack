"""DrumSep MDX23C model service.

Downloads and runs the DrumSep 5-stem model to separate a drum track
into kick, snare, toms, hh, and cymbals.

Uses the MDX23C architecture from MSST (ZFTurbo/Music-Source-Separation-Training)
with the model class embedded locally — no MSST package dependency.
"""

import logging
from pathlib import Path

import httpx
import numpy as np
import soundfile as sf
import torch
import torch.nn as nn
import yaml
from ml_collections import ConfigDict

from app.ml.mdx23c import TFC_TDF_net

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).resolve().parents[2] / "models" / "drumsep"
CONFIG_URL = "https://github.com/jarredou/models/releases/download/DrumSep/config_mdx23c.yaml"
CKPT_URL = "https://github.com/jarredou/models/releases/download/DrumSep/drumsep_5stems_mdx23c_jarredou.ckpt"
CONFIG_PATH = MODEL_DIR / "config_mdx23c.yaml"
CKPT_PATH = MODEL_DIR / "drumsep_5stems_mdx23c_jarredou.ckpt"

STEM_NAMES = ["kick", "snare", "toms", "hh", "cymbals"]

# Cached model
_model = None
_config = None


def download_model_files() -> None:
    """Download YAML config and CKPT weights if not already present."""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    for url, path in [(CONFIG_URL, CONFIG_PATH), (CKPT_URL, CKPT_PATH)]:
        if path.exists():
            logger.info(f"Model file already exists: {path.name}")
            continue
        logger.info(f"Downloading {path.name} from {url}...")
        with httpx.stream("GET", url, follow_redirects=True, timeout=600) as resp:
            resp.raise_for_status()
            with open(path, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=8192):
                    f.write(chunk)
        logger.info(f"Downloaded {path.name} ({path.stat().st_size / 1e6:.1f} MB)")


def _get_model():
    """Load the MDX23C model from config + checkpoint (cached globally)."""
    global _model, _config

    if _model is not None:
        return _model, _config

    download_model_files()

    # Load config as ConfigDict (dotted-attribute access, same as MSST)
    with open(CONFIG_PATH) as f:
        config = ConfigDict(yaml.load(f, Loader=yaml.FullLoader))
    _config = config

    # Build model from config
    model = TFC_TDF_net(config)

    # Load checkpoint — unwrap state_dict if wrapped
    logger.info("Loading DrumSep checkpoint...")
    checkpoint = torch.load(CKPT_PATH, map_location="cpu", weights_only=False)
    if "state" in checkpoint:
        checkpoint = checkpoint["state"]
    if "state_dict" in checkpoint:
        checkpoint = checkpoint["state_dict"]
    if "model_state_dict" in checkpoint:
        checkpoint = checkpoint["model_state_dict"]
    model.load_state_dict(checkpoint)
    model.eval()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device)
    logger.info(f"DrumSep model loaded on {device}")

    _model = model
    return _model, _config


def separate_drums(drum_path: Path, output_dir: Path) -> dict[str, Path]:
    """Separate a drum track into 5 individual instrument stems.

    Returns dict mapping stem name to output WAV path.
    """
    model, config = _get_model()
    device = next(model.parameters()).device

    # Load audio
    logger.info(f"Loading drum audio for DrumSep: {drum_path}")
    audio, sr = sf.read(str(drum_path), dtype="float32")
    if audio.ndim == 1:
        audio = np.stack([audio, audio], axis=-1)  # mono -> stereo
    # audio shape: (samples, channels)

    target_sr = config.audio.get("sample_rate", 44100)
    if sr != target_sr:
        import librosa

        audio_left = librosa.resample(audio[:, 0], orig_sr=sr, target_sr=target_sr)
        audio_right = librosa.resample(audio[:, 1], orig_sr=sr, target_sr=target_sr)
        audio = np.stack([audio_left, audio_right], axis=-1)
        sr = target_sr

    # Convert to tensor: (channels, samples) — what demix expects
    mix = audio.T  # (channels, samples)

    # Determine instruments from config
    if getattr(config.training, "target_instrument", None):
        instruments = [config.training.target_instrument]
    else:
        instruments = list(config.training.instruments)
    logger.info(f"DrumSep instruments: {instruments}")

    # Run demix
    logger.info("Running DrumSep inference...")
    stem_dict = _demix(config, model, mix, device)

    # Save stems
    output_dir.mkdir(parents=True, exist_ok=True)
    stem_paths: dict[str, Path] = {}

    for stem_name, stem_audio in stem_dict.items():
        # stem_audio shape: (channels, samples)
        stem_path = output_dir / f"{stem_name}.wav"
        sf.write(str(stem_path), stem_audio.T, sr)
        stem_paths[stem_name] = stem_path
        logger.info(f"Saved stem: {stem_name} -> {stem_path}")

    return stem_paths


def _get_windowing_array(window_size: int, fade_size: int) -> torch.Tensor:
    """Create a fade-in/fade-out window for overlap-add blending."""
    fadein = torch.linspace(0, 1, fade_size)
    fadeout = torch.linspace(1, 0, fade_size)
    window = torch.ones(window_size)
    window[:fade_size] = fadein
    window[-fade_size:] = fadeout
    return window


def _demix(
    config: ConfigDict,
    model: nn.Module,
    mix: np.ndarray,
    device: str,
) -> dict[str, np.ndarray]:
    """Run chunked overlap-add inference on a stereo mix.

    Adapted from MSST's demix() for MDX23C (generic mode).

    Args:
        config: Model config (ConfigDict with dotted access)
        model: The MDX23C model
        mix: numpy array of shape (channels, samples)
        device: torch device string

    Returns:
        Dict mapping instrument name to numpy array (channels, samples).
    """
    mix = torch.tensor(mix, dtype=torch.float32)

    # Read inference params from config
    if hasattr(config.inference, "chunk_size"):
        chunk_size = config.inference.chunk_size
    else:
        chunk_size = config.audio.chunk_size
    num_overlap = config.inference.num_overlap
    batch_size = config.inference.batch_size

    if getattr(config.training, "target_instrument", None):
        instruments = [config.training.target_instrument]
    else:
        instruments = list(config.training.instruments)
    num_instruments = len(instruments)

    fade_size = chunk_size // 10
    step = chunk_size // num_overlap
    border = chunk_size - step
    length_init = mix.shape[-1]
    windowing_array = _get_windowing_array(chunk_size, fade_size)

    # Reflect-pad edges to avoid border artifacts
    if length_init > 2 * border and border > 0:
        mix = nn.functional.pad(mix, (border, border), mode="reflect")

    use_amp = getattr(config.training, "use_amp", True)

    with torch.amp.autocast("cuda", enabled=(use_amp and device != "cpu")):
        with torch.inference_mode():
            req_shape = (num_instruments,) + mix.shape
            result = torch.zeros(req_shape, dtype=torch.float32)
            counter = torch.zeros(req_shape, dtype=torch.float32)

            i = 0
            batch_data = []
            batch_locations = []

            while i < mix.shape[1]:
                part = mix[:, i : i + chunk_size].to(device)
                chunk_len = part.shape[-1]
                if chunk_len > chunk_size // 2:
                    pad_mode = "reflect"
                else:
                    pad_mode = "constant"
                part = nn.functional.pad(part, (0, chunk_size - chunk_len), mode=pad_mode, value=0)

                batch_data.append(part)
                batch_locations.append((i, chunk_len))
                i += step

                # Process batch when full or at end
                if len(batch_data) >= batch_size or i >= mix.shape[1]:
                    arr = torch.stack(batch_data, dim=0)
                    x = model(arr)

                    window = windowing_array.clone()
                    if batch_locations[0][0] == 0:  # first chunk, no fade-in
                        window[:fade_size] = 1
                    if i >= mix.shape[1]:  # last chunk, no fade-out
                        window[-fade_size:] = 1

                    for j, (start, seg_len) in enumerate(batch_locations):
                        result[..., start : start + seg_len] += (
                            x[j, ..., :seg_len].cpu() * window[..., :seg_len]
                        )
                        counter[..., start : start + seg_len] += window[..., :seg_len]

                    batch_data.clear()
                    batch_locations.clear()

            # Weighted average
            estimated_sources = result / counter
            estimated_sources = estimated_sources.cpu().numpy()
            np.nan_to_num(estimated_sources, copy=False, nan=0.0)

            # Remove reflect padding
            if length_init > 2 * border and border > 0:
                estimated_sources = estimated_sources[..., border:-border]

    return {k: v for k, v in zip(instruments, estimated_sources)}
