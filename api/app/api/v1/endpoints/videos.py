from app.api.deps import SessionDep
from app.api.uploads import TrackForm, VideoForm, VideoMetaForm, read_video
from app.schemas.video import VideoResponse
from app.services import ingest as ingest_service
from fastapi import APIRouter

router = APIRouter(prefix="/videos", tags=["videos"])


@router.post("", response_model=VideoResponse)
def upload_video(
    db: SessionDep,
    video: VideoForm,
    track: TrackForm = None,
    meta: VideoMetaForm = "{}",
):
    """Upload a street video (up to MAX_VIDEO_MB), with a way to place its frames on the map.

    Frame positions come from, in order: the `track` GPX if sent, the GPS stored in the video
    (GoPro, DJI, dashcams...), or `meta.route`, the path drawn on a map (approximate). With none
    of these ML refuses the video (422 `no_location`). `location_source` in the response says
    which one was used.

    The ML service picks one frame every `spacing_m` metres, places it, blurs it and detects
    elements, like for an uploaded image (`source` "video", one `sequence_id`, `frame_index`
    0, 1, 2…). The video itself is never saved. Synchronous: can take minutes.
    501 while ML doesn't offer video yet.
    """
    return ingest_service.ingest_video(db, read_video(video, track, meta))
