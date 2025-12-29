from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
import tempfile
import os
import base64
import logging
import subprocess
import json

app = FastAPI()
logging.basicConfig(level=logging.INFO)

API_KEY = os.environ.get("API_KEY", "")


class DownloadRequest(BaseModel):
    url: str
    audio_only: bool = False


class DownloadResponse(BaseModel):
    filename: str
    file_base64: str
    size_mb: float
    title: str
    duration_seconds: int


def verify_key(x_api_key: str = Header(None)):
    if not API_KEY or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


@app.get("/")
async def root():
    return {"status": "ok", "service": "yt-download-api"}


@app.post("/download")
async def download_video(request: DownloadRequest, x_api_key: str = Header(...)):
    verify_key(x_api_key)
    try:
        logging.info(f"Downloading: {request.url}")

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_template = os.path.join(tmp_dir, "%(id)s.%(ext)s")
            
            # Build yt-dlp command
            cmd = [
                "yt-dlp",
                "--no-playlist",
                "-o", output_template,
                "--print-json",
            ]
            
            if request.audio_only:
                cmd.extend(["-x", "--audio-format", "mp3"])
            else:
                cmd.extend(["-f", "best[height<=720][ext=mp4]/best[height<=720]/best"])
            
            cmd.append(request.url)
            
            # Run yt-dlp
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logging.error(f"yt-dlp error: {result.stderr}")
                raise HTTPException(status_code=500, detail=f"Download failed: {result.stderr}")
            
            # Parse video info from JSON output
            video_info = json.loads(result.stdout)
            
            # Find the downloaded file
            files = os.listdir(tmp_dir)
            if not files:
                raise HTTPException(status_code=500, detail="No file downloaded")
            
            filepath = os.path.join(tmp_dir, files[0])
            file_size = os.path.getsize(filepath) / (1024 * 1024)
            
            if file_size > 50:
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large ({file_size:.1f}MB). Max 50MB.",
                )
            
            with open(filepath, "rb") as f:
                file_base64 = base64.b64encode(f.read()).decode()
            
            return DownloadResponse(
                filename=files[0],
                file_base64=file_base64,
                size_mb=round(file_size, 2),
                title=video_info.get("title", "Unknown"),
                duration_seconds=video_info.get("duration", 0),
            )

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/info")
async def get_info(url: str, x_api_key: str = Header(...)):
    verify_key(x_api_key)
    try:
        cmd = ["yt-dlp", "--dump-json", "--no-playlist", url]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Failed to get info: {result.stderr}")
        
        info = json.loads(result.stdout)
        
        return {
            "title": info.get("title"),
            "duration_seconds": info.get("duration"),
            "author": info.get("uploader"),
            "views": info.get("view_count"),
            "thumbnail_url": info.get("thumbnail"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
