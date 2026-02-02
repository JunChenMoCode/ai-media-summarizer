import asyncio
import os
import tempfile
import uuid

from fastapi import APIRouter, HTTPException, Request as FastAPIRequest

from fast_video_summary import FastVideoAnalyzer

from .minio_store import (
    extract_job_id_from_object_key,
    minio_download_to_file,
    minio_object_exists,
    minio_object_key,
    minio_presigned_url,
    minio_upload_file,
    normalize_video_object_key,
    minio_enabled,
)
from .models import CaptureRequest

router = APIRouter()


@router.post("/capture_frame")
async def capture_frame(req: FastAPIRequest, request: CaptureRequest):
    """
    从视频中按时间点截取一帧，并把图片上传到 MinIO 后返回可访问 URL。

    设计要点：
    - 前端只需要一个 URL，就能展示当前帧；
    - 计算产物写入临时目录，避免在项目目录产生 fast_output 等落盘目录；
    - 读取视频优先走 presigned URL；必要时才临时下载到本地文件再处理。
    """
    print(f">>> Capturing frame for {request.video_filename} at {request.timestamp}s...")
    rel_video_path = (request.video_filename or "").replace("\\", "/").lstrip("/")

    if not minio_enabled():
        raise HTTPException(status_code=404, detail="Video file not found")

    video_object_key = normalize_video_object_key(rel_video_path)
    if not minio_object_exists(video_object_key):
        raise HTTPException(status_code=404, detail="Video file not found")

    job_id = extract_job_id_from_object_key(video_object_key) or str(uuid.uuid4())
    video_source = minio_presigned_url(video_object_key)

    with tempfile.TemporaryDirectory(prefix="leader-cap-") as temp_out:
        output_dir = os.path.join(temp_out, job_id)
        analyzer = FastVideoAnalyzer(video_path=video_source, output_dir=output_dir, config={})
        loop = asyncio.get_event_loop()
        try:
            image_path = await loop.run_in_executor(None, lambda: analyzer.capture_frame(timestamp=request.timestamp))
        except Exception:
            # 部分环境下 ffmpeg 读 presigned URL 可能失败：临时下载后重试
            with tempfile.NamedTemporaryFile(prefix="leader-video-", suffix=".mp4", delete=False) as tf:
                local_fallback_path = tf.name
            try:
                minio_download_to_file(video_object_key, local_fallback_path)
                analyzer = FastVideoAnalyzer(video_path=local_fallback_path, output_dir=output_dir, config={})
                image_path = await loop.run_in_executor(None, lambda: analyzer.capture_frame(timestamp=request.timestamp))
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
            finally:
                try:
                    os.remove(local_fallback_path)
                except Exception:
                    pass

        if not image_path:
            raise HTTPException(status_code=500, detail="Failed to capture frame")

        p_normalized = image_path.replace(os.sep, "/")
        object_key = minio_object_key("outputs", job_id, p_normalized)
        url = minio_upload_file(os.path.join(output_dir, image_path), object_key, content_type="image/jpeg")
        return {"url": url, "timestamp": request.timestamp}

