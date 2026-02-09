import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.models.cluster import ClusterInfo, ClusterUpdateRequest, ClustersResponse
from app.models.drum_event import DrumEvent
from app.models.job import JobResponse
from app.services.drum_clusterer import deduplicate_events, relabel_and_regenerate
from app.services.midi_writer import write_midi
from app.storage.file_manager import file_manager
from app.storage.job_store import job_store

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
    """Get job status and progress."""
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse(**job.model_dump())


@router.get("/{job_id}/midi")
async def download_midi(job_id: str):
    """Download the generated MIDI file."""
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    midi_path = file_manager.midi_path(job_id)
    if not midi_path.exists():
        raise HTTPException(status_code=404, detail="MIDI file not ready")

    return FileResponse(
        midi_path,
        media_type="audio/midi",
        filename=f"drums_{job_id[:8]}.mid",
    )


@router.get("/{job_id}/other-track")
async def download_other_track(job_id: str):
    """Download the non-drum backing track."""
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    other_path = file_manager.other_path(job_id)
    if not other_path.exists():
        raise HTTPException(status_code=404, detail="Backing track not ready")

    return FileResponse(
        other_path,
        media_type="audio/mpeg",
        filename=f"backing_{job_id[:8]}.mp3",
    )


@router.get("/{job_id}/drum-track")
async def download_drum_track(job_id: str):
    """Download the isolated drum track."""
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    drum_path = file_manager.drum_path(job_id)
    if not drum_path.exists():
        raise HTTPException(status_code=404, detail="Drum track not ready")

    return FileResponse(
        drum_path,
        media_type="audio/mpeg",
        filename=f"drums_{job_id[:8]}.mp3",
    )


@router.get("/{job_id}/events")
async def get_events(job_id: str):
    """Get classified drum events as JSON."""
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    events_path = file_manager.events_path(job_id)
    if not events_path.exists():
        raise HTTPException(status_code=404, detail="Events not ready")

    return json.loads(events_path.read_text())


@router.get("/{job_id}/clusters", response_model=ClustersResponse)
async def get_clusters(job_id: str):
    """Get cluster info and events for the job."""
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    clusters_path = file_manager.clusters_path(job_id)
    if not clusters_path.exists():
        raise HTTPException(status_code=404, detail="Clusters not ready")

    events_path = file_manager.events_path(job_id)
    if not events_path.exists():
        raise HTTPException(status_code=404, detail="Events not ready")

    clusters_data = json.loads(clusters_path.read_text())
    events_data = json.loads(events_path.read_text())

    return ClustersResponse(
        clusters=[ClusterInfo(**c) for c in clusters_data],
        events=events_data,
    )


@router.put("/{job_id}/clusters", response_model=ClustersResponse)
async def update_clusters(job_id: str, req: ClusterUpdateRequest):
    """Update cluster labels, re-dedup, and regenerate MIDI."""
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    clusters_path = file_manager.clusters_path(job_id)
    events_path = file_manager.events_path(job_id)
    if not clusters_path.exists() or not events_path.exists():
        raise HTTPException(status_code=404, detail="Clusters/events not ready")

    # Load current data
    clusters = [ClusterInfo(**c) for c in json.loads(clusters_path.read_text())]
    events = [DrumEvent(**e) for e in json.loads(events_path.read_text())]

    # Re-label and regenerate
    events, clusters = relabel_and_regenerate(
        events, clusters, req.cluster_labels, job.bpm
    )

    # Save updated events
    events_data = [e.model_dump() for e in events]
    events_path.write_text(json.dumps(events_data, indent=2))

    # Save updated clusters
    clusters_data = [c.model_dump() for c in clusters]
    clusters_path.write_text(json.dumps(clusters_data, indent=2))

    # Regenerate MIDI
    midi_path = file_manager.midi_path(job_id)
    write_midi(events, job.bpm, midi_path)

    return ClustersResponse(
        clusters=clusters,
        events=events_data,
    )
