import asyncio
import json
import os
import tempfile
import uuid
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request as FastAPIRequest
from fastapi.responses import StreamingResponse

from fast_video_summary import FastVideoAnalyzer

from .minio_store import (
    extract_job_id_from_object_key,
    minio_download_to_file,
    minio_enabled,
    minio_object_exists,
    minio_object_key,
    minio_presigned_url,
    minio_upload_tree,
    normalize_video_object_key,
)
from .models import AnalyzePathRequest

router = APIRouter()


@router.post("/analyze_path")
async def analyze_video_by_path(req: FastAPIRequest, request: AnalyzePathRequest):
    """
    启动一次视频分析，并用“流式输出”把进度推给前端。

    输入 video_path 支持两种模式：
    1) MinIO 对象路径（推荐）
       - uploads/<job_id>/<filename> 或 <job_id>/<filename>
       - 服务端会生成 presigned url 作为 analyzer 的 video_source
    2) 直接可访问的 http(s) 视频 URL（比如公网链接）
       - 用 URL 作为 analyzer 的 video_source

    输出是 text/event-stream（但内容格式上更像逐行 JSON），前端会按行解析：
    - {"status":"progress","message":"..."}
    - {"status":"success", ...}
    - {"status":"error", ...}
    """

    async def event_generator():
        try:
            config = request.config.model_dump()
            yield json.dumps({"status": "progress", "message": "视频加载成功，开始分析..."}) + "\n"

            queue: asyncio.Queue[str] = asyncio.Queue()
            video_object_key = ""
            job_id = ""
            video_source = ""
            video_url = ""
            local_fallback_path = ""

            video_ref = (request.video_path or "").strip()
            parsed = urlparse(video_ref)

            if parsed.scheme in ("http", "https"):
                # 直接用 URL 作为输入源（不依赖 MinIO）
                job_id = str(uuid.uuid4())
                video_source = video_ref
                video_url = video_ref
            else:
                # 默认认为是 MinIO 的对象引用
                if not minio_enabled():
                    raise RuntimeError("MinIO 未启用，无法分析视频")

                rel_url_path = video_ref.replace("\\", "/").lstrip("/")
                video_object_key = normalize_video_object_key(rel_url_path)
                if not minio_object_exists(video_object_key):
                    raise RuntimeError("视频文件不存在")

                job_id = extract_job_id_from_object_key(video_object_key) or str(uuid.uuid4())
                # analyzer 接收的是“可读取”的视频源，这里用 presigned GET URL
                video_source = minio_presigned_url(video_object_key)
                video_url = minio_presigned_url(video_object_key)

            # 所有产物都写到临时目录，分析结束后统一上传到 MinIO
            with tempfile.TemporaryDirectory(prefix="leader-out-") as temp_out:
                output_dir = os.path.join(temp_out, job_id)
                analyzer = FastVideoAnalyzer(
                    video_source,
                    output_dir,
                    config=config,
                    progress_callback=lambda m: queue.put_nowait(m),
                )
                task = asyncio.create_task(asyncio.to_thread(analyzer.run))

                while not task.done() or not queue.empty():
                    try:
                        msg = await asyncio.wait_for(queue.get(), timeout=0.5)
                        yield json.dumps({"status": "progress", "message": msg}) + "\n"
                    except asyncio.TimeoutError:
                        continue

                ai_analysis = task.result()

                # 少数情况下 analyzer 读取 presigned URL 可能失败（取决于 ffmpeg/网络）
                # 这里保留旧逻辑：失败时把视频下载到临时文件再跑一次。
                if not ai_analysis and video_object_key:
                    with tempfile.NamedTemporaryFile(prefix="leader-video-", suffix=".mp4", delete=False) as tf:
                        local_fallback_path = tf.name
                    try:
                        minio_download_to_file(video_object_key, local_fallback_path)
                        queue = asyncio.Queue()
                        analyzer = FastVideoAnalyzer(
                            local_fallback_path,
                            output_dir,
                            config=config,
                            progress_callback=lambda m: queue.put_nowait(m),
                        )
                        task = asyncio.create_task(asyncio.to_thread(analyzer.run))
                        while not task.done() or not queue.empty():
                            try:
                                msg = await asyncio.wait_for(queue.get(), timeout=0.5)
                                yield json.dumps({"status": "progress", "message": msg}) + "\n"
                            except asyncio.TimeoutError:
                                continue
                        ai_analysis = task.result()
                    finally:
                        try:
                            os.remove(local_fallback_path)
                        except Exception:
                            pass

                if not ai_analysis:
                    yield json.dumps({"status": "error", "message": "分析失败，无法生成报告"}) + "\n"
                    return

                report_path = os.path.join(output_dir, "final_report.md")
                yield json.dumps({"status": "progress", "message": "正在上传分析产物到 MinIO..."}) + "\n"
                minio_upload_tree(output_dir, minio_object_key("outputs", job_id))

                with open(report_path, "r", encoding="utf-8") as f:
                    report_content = f.read()

                # 将 report 中的相对图片链接替换为 presigned URL，前端可直接渲染
                for seg in ai_analysis.get("segments", []):
                    if "image_path" in seg:
                        image_object_key = minio_object_key("outputs", job_id, seg["image_path"])
                        seg["image_url"] = minio_presigned_url(image_object_key)
                        report_content = report_content.replace(f"]({seg['image_path']})", f"]({seg['image_url']})")

                yield json.dumps(
                    {
                        "status": "success",
                        "report": report_content,
                        "data": ai_analysis,
                        "video_url": video_url,
                        "video_path": video_object_key or video_ref,
                        "object_key": video_object_key,
                        "outputs_base_url": "minio",
                    }
                ) + "\n"
        except Exception as e:
            print(f"Error during analysis: {e}")
            yield json.dumps({"status": "error", "message": str(e)}) + "\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

