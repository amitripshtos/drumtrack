import asyncio
import hashlib
import json
import logging
import shutil
from pathlib import Path

from app.models.job import JobStatus
from app.services import lalal, youtube
from app.services import demucs as demucs_service
from app.services.drum_clusterer import detect_cluster_and_label
from app.services.midi_writer import write_midi
from app.storage.file_manager import file_manager
from app.storage.job_store import job_store

logger = logging.getLogger(__name__)


async def run_pipeline(job_id: str) -> None:
    """Run the full processing pipeline for a job."""
    try:
        job = job_store.get(job_id)
        if job is None:
            return

        original_path = file_manager.original_path(job_id)

        # Step 1: Download from YouTube if needed
        if job.source == "youtube" and job.source_url:
            job_store.update_status(job_id, JobStatus.downloading_youtube, progress=5)
            logger.info(f"Downloading YouTube: {job.source_url}")
            await asyncio.to_thread(
                youtube.download_youtube, job.source_url, original_path
            )
            # Update job title with actual video title
            video_title = await asyncio.to_thread(
                youtube.get_video_title, job.source_url
            )
            if video_title:
                job.title = video_title
                job_store._persist(job)
            # Compute audio hash for dedup (uploads already have it set)
            audio_bytes = await asyncio.to_thread(original_path.read_bytes)
            job.audio_hash = hashlib.sha256(audio_bytes).hexdigest()

        # Step 2: Stem separation (with dedup check)
        drum_path = file_manager.drum_path(job_id)
        other_path = file_manager.other_path(job_id)

        # Check if stems already exist from a previous job with the same audio
        existing_job = None
        if job.audio_hash:
            existing_job = job_store.find_by_audio_hash(job.audio_hash, exclude_id=job_id)

        if existing_job:
            logger.info(f"Reusing stems from job {existing_job.id} (same audio hash)")
            job_store.update_status(job_id, JobStatus.separating_stems, progress=15)
            src_drum = file_manager.drum_path(existing_job.id)
            src_other = file_manager.other_path(existing_job.id)
            await asyncio.to_thread(shutil.copy2, src_drum, drum_path)
            await asyncio.to_thread(shutil.copy2, src_other, other_path)
            job_store.update_status(job_id, JobStatus.separating_stems, progress=50)
        elif job.separator == "lalal":
            # LALAL.AI cloud separation
            job_store.update_status(job_id, JobStatus.uploading_to_lalal, progress=15)
            logger.info("Uploading to LALAL.AI...")
            file_id = await lalal.upload_file(original_path)

            job_store.update_status(job_id, JobStatus.separating_stems, progress=25)
            logger.info("Starting stem separation...")
            await lalal.start_split(file_id)

            result = await lalal.poll_until_done(file_id)
            job_store.update_status(job_id, JobStatus.separating_stems, progress=50)

            await lalal.download_stems(result, drum_path, other_path)
        else:
            # Demucs local separation (default)
            job_store.update_status(job_id, JobStatus.separating_stems, progress=15)
            logger.info("Running Demucs local stem separation...")
            await asyncio.to_thread(
                demucs_service.separate, original_path, drum_path, other_path
            )
            job_store.update_status(job_id, JobStatus.separating_stems, progress=50)

        # Step 3: Separate drum track into individual instruments
        job_store.update_status(job_id, JobStatus.separating_drum_instruments, progress=55)
        logger.info("Separating drum instruments (kick, snare, toms, hh, cymbals)...")

        # Step 4: Detect onsets per stem
        job_store.update_status(job_id, JobStatus.detecting_onsets, progress=65)
        logger.info("Detecting onsets per drum stem...")

        events, clusters = await asyncio.to_thread(
            detect_cluster_and_label, drum_path, job.bpm
        )

        # Save events to JSON
        events_path = file_manager.events_path(job_id)
        events_data = [e.model_dump() for e in events]
        events_path.write_text(json.dumps(events_data, indent=2))

        # Save clusters to JSON
        clusters_path = file_manager.clusters_path(job_id)
        clusters_data = [c.model_dump() for c in clusters]
        clusters_path.write_text(json.dumps(clusters_data, indent=2))

        # Step 7: Generate MIDI
        job_store.update_status(job_id, JobStatus.generating_midi, progress=85)
        logger.info("Generating MIDI...")
        midi_path = file_manager.midi_path(job_id)
        await asyncio.to_thread(write_midi, events, job.bpm, midi_path)

        # Done
        job_store.update_status(job_id, JobStatus.complete, progress=100)
        logger.info(f"Job {job_id} complete!")

    except Exception as e:
        logger.exception(f"Pipeline failed for job {job_id}")
        job_store.update_status(job_id, JobStatus.failed, error=str(e))
