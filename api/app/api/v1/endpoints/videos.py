from fastapi import APIRouter

from app.api.deps import SessionDep
from app.api.uploads import TrackForm, VideoForm, VideoMetaForm, read_video
from app.schemas.video import VideoResponse
from app.services import ingest as ingest_service

router = APIRouter(prefix="/videos", tags=["videos"])


@router.post("", response_model=VideoResponse)
def upload_video(
    db: SessionDep,
    video: VideoForm,
    track: TrackForm,
    meta: VideoMetaForm = "{}",
):
    """Upload a street video (up to MAX_VIDEO_MB) with its GPS track.

    Frame positions come from the `track` GPX recorded with the video (required).

    The API keeps one frame every `spacing_m` metres of travel (at most MAX_VIDEO_FRAMES) and
    sends each one to ML /infer like an uploaded image (`source` "video", one `sequence_id`,
    `frame_index` 0, 1, 2…): blurred, detected, stored, then one dedup for the whole video.
    The video itself is never kept. Synchronous: can take minutes.
    """
    return ingest_service.ingest_video(db, read_video(video, track, meta))
