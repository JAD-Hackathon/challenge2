from __future__ import annotations

from pathlib import Path

import typer

from src.config import get_settings
from src.io.video.extraction import extract_video_frames

app = typer.Typer(
    name="ml",
    help="Aveiro Tech City ML CLI tools.",
    no_args_is_help=True,
)


@app.command("extract-frames")
def extract_frames_cmd(
    video: Path = typer.Argument(
        ..., exists=True, dir_okay=False, help="Path to MP4/MOV video file."
    ),
    gpx: Path = typer.Argument(
        ..., exists=True, dir_okay=False, help="Path to GPX track file."
    ),
    step_m: float = typer.Option(
        5.0, "--step-m", help="Sampling interval in metres along track."
    ),
    sequence_id: str | None = typer.Option(
        None, "--sequence-id", help="Optional sequence UUID/name."
    ),
    fov: float | None = typer.Option(
        None, "--fov", help="Horizontal camera FOV in degrees."
    ),
    camera_height_m: float | None = typer.Option(
        None, "--camera-height", help="Camera height above ground (m)."
    ),
    time_offset_s: float = typer.Option(
        0.0, "--time-offset", help="Seconds to add to GPX time to align with video."
    ),
    api_url: str | None = typer.Option(
        None,
        "--api-url",
        help="ML service URL (e.g. http://localhost:8001) to stream frames directly to /infer.",
    ),
    meta_out: Path | None = typer.Option(
        None, "--meta-out", help="Optional JSONL path to write CameraMeta records."
    ),
) -> None:
    """Extract georeferenced frames every ~5m, redact PII in RAM, and save only to shared_dir/images."""
    metas = extract_video_frames(
        video_path=video,
        gpx_path=gpx,
        step_m=step_m,
        sequence_id=sequence_id,
        fov=fov,
        camera_height_m=camera_height_m,
        time_offset_s=time_offset_s,
        api_url=api_url,
        meta_out=meta_out,
    )
    seq = metas[0]["sequence_id"] if metas else "n/a"
    target = f"POST {api_url}/infer" if api_url else get_settings().paths.images_dir
    typer.echo(
        f"Processed {len(metas)} redacted frames (sequence_id={seq} -> {target})."
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
