from pydantic import BaseModel


class ClusterInfo(BaseModel):
    id: int
    suggested_label: str  # auto-heuristic suggestion
    label: str  # current active label
    suggestion_confidence: float
    event_count: int
    mean_velocity: float
    representative_time: float  # time of event closest to cluster centroid


class ClusterUpdateRequest(BaseModel):
    cluster_labels: dict[str, str]  # {cluster_id_str: drum_type}


class ClustersResponse(BaseModel):
    clusters: list[ClusterInfo]
    events: list[dict]  # DrumEvent dicts with cluster_id
