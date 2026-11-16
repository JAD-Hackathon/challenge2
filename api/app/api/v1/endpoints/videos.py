from app.api.deps import SessionDep
from app.api.uploads import TrackForm, VideoForm, VideoMetaForm, read_video
from app.schemas.video import VideoResponse
from app.services import ingest as ingest_service
from fastapi import APIRouter

router = APIRouter(prefix="/videos", tags=["videos"])


@router.post("", response_model=VideoResponse)
def upload_video(db: SessionDep, video: VideoForm, track: TrackForm, meta: VideoMetaForm = "{}"):
    """Upload a street video (up to MAX_VIDEO_MB) plus the GPS track (GPX) recorded with it.

    The ML service picks one frame every `spacing_m` metres, places it with the GPS track, blurs
    it and detects elements, like for an uploaded image (`source` "video", one `sequence_id`,
    `frame_index` 0, 1, 2…). The video itself is never saved. Synchronous: can take minutes.
    501 while ML doesn't offer video yet.
    """
    return ingest_service.ingest_video(db, read_video(video, track, meta))
