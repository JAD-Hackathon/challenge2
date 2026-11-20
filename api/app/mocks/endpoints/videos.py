from app.api.uploads import TrackForm, VideoForm, VideoMetaForm, read_video
from app.api.v1.endpoints import videos as real
from app.mocks.endpoints import mirrors
from app.mocks.services import images as service
from app.schemas.video import VideoResponse
from fastapi import APIRouter

router = APIRouter(prefix="/videos", tags=["videos"])


@router.post("", response_model=VideoResponse)
@mirrors(real.upload_video)
def upload_video(video: VideoForm, track: TrackForm, meta: VideoMetaForm = "{}"):
    return service.ingest_video(read_video(video, track, meta))
