import logging
from pathlib import Path

import torch
import numpy as np
import soundfile as sf

logger = logging.getLogger(__name__)

# Cache the model across calls
_model = None


def _get_model():
    global _model
    if _model is None:
        from demucs.pretrained import get_model

        logger.info("Loading htdemucs model (first call, may download weights)...")
        _model = get_model("htdemucs")
        _model.eval()
        if torch.cuda.is_available():
            _model.cuda()
    return _model


def separate(input_path: Path, drum_path: Path, other_path: Path) -> None:
    """Separate audio into drums and other stems using Demucs htdemucs model.

    The htdemucs model outputs 4 sources: drums, bass, other, vocals.
    We save the drums stem and mix the remaining 3 into the 'other' track.
    """
    from demucs.apply import apply_model
    from demucs.audio import AudioFile

    model = _get_model()
    device = next(model.parameters()).device

    # Load audio
    logger.info(f"Loading audio from {input_path}")
    audio = AudioFile(input_path).read(streams=0, samplerate=model.samplerate, channels=model.audio_channels)
    # audio shape: (channels, samples)

    ref = audio.mean(0)
    audio = (audio - ref.mean()) / ref.std()

    # Run model — expects (batch, channels, samples)
    audio_tensor = audio.unsqueeze(0).to(device)

    logger.info("Running Demucs separation...")
    with torch.no_grad():
        sources = apply_model(model, audio_tensor, progress=False)
    # sources shape: (batch, num_sources, channels, samples)
    sources = sources[0]  # remove batch dim

    # Undo normalization
    sources = sources * ref.std() + ref.mean()

    # Map source names to indices
    source_names = model.sources  # e.g. ['drums', 'bass', 'other', 'vocals']
    source_map = {name: i for i, name in enumerate(source_names)}
    logger.info(f"Demucs sources: {source_names}")

    # Extract drums
    drums = sources[source_map["drums"]].cpu().numpy()

    # Mix everything else (bass + other + vocals) into the backing track
    other_indices = [i for name, i in source_map.items() if name != "drums"]
    other_mix = sum(sources[i] for i in other_indices).cpu().numpy()

    # Save as WAV files
    logger.info(f"Saving drum stem to {drum_path}")
    sf.write(str(drum_path), drums.T, model.samplerate)

    logger.info(f"Saving other stem to {other_path}")
    sf.write(str(other_path), other_mix.T, model.samplerate)

    logger.info("Demucs separation complete")
