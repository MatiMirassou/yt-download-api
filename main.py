from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pytubefix import YouTube
import tempfile
import os
import base64
import logging

app = FastAPI()
logging.basicConfig(level=logging.INFO)


class DownloadRequest(BaseModel):
    url: str
    audio_only: bool = False


class DownloadResponse(BaseModel):
    filename: str
    file_base64: str
    size_mb: float
    title: str
    duration_seconds: int


@app.get("/")
async def root():
    return {"status": "ok", "service": "yt-download-api"}


@app.post("/download")
async def download_video(request: DownloadRequest):
    try:
        logging.info(f"Downloading: {request.url}")
        yt = YouTube(request.url)

        if request.audio_only:
            stream = yt.streams.filter(only_audio=True).order_by("abr").desc().first()
        else:
            stream = (
                yt.streams.filter(progressive=True, file_extension="mp4")
                .order_by("resolution")
                .desc()
                .first()
            )

        if not stream:
            raise HTTPException(status_code=400, detail="No suitable stream found")

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = stream.download(output_path=tmp_dir)
            file_size = os.path.getsize(path) / (1024 * 1024)

            if file_size > 50:
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large ({file_size:.1f}MB). Max 50MB for base64 response.",
                )

            with open(path, "rb") as f:
                file_base64 = base64.b64encode(f.read()).decode()

            return DownloadResponse(
                filename=os.path.basename(path),
                file_base64=file_base64,
                size_mb=round(file_size, 2),
                title=yt.title,
                duration_seconds=yt.length,
            )

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/info")
async def get_info(url: str):
    """Get video metadata without downloading"""
    try:
        yt = YouTube(url)
        streams = yt.streams.filter(progressive=True, file_extension="mp4")

        return {
            "title": yt.title,
            "duration_seconds": yt.length,
            "author": yt.author,
            "views": yt.views,
            "thumbnail_url": yt.thumbnail_url,
            "available_resolutions": [s.resolution for s in streams],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))