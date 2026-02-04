import asyncio
import hashlib
import json
import os
import re
import tempfile
import uuid
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Query, Request as FastAPIRequest
from fastapi.responses import StreamingResponse

from fast_video_summary import FastVideoAnalyzer

from .minio_store import (
    extract_job_id_from_object_key,
    minio_download_to_file,
    minio_enabled,
    minio_object_exists,
    minio_object_etag_md5,
    minio_object_key,
    minio_presigned_url,
    minio_upload_tree,
    normalize_video_object_key,
    minio_remove_object,
    minio_remove_folder,
)
from .models import AnalyzePathRequest

router = APIRouter()


def _file_md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _download_url_to_file(url: str, path: str) -> None:
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp, open(path, "wb") as out:
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)


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
            video_md5 = ""
            source_kind = ""
            source_ref = ""

            video_ref = (request.video_path or "").strip()
            parsed = urlparse(video_ref)

            if parsed.scheme in ("http", "https"):
                job_id = str(uuid.uuid4())
                video_url = video_ref
                source_kind = "url"
                source_ref = video_ref
            else:
                if not minio_enabled():
                    raise RuntimeError("MinIO 未启用，无法分析视频")

                rel_url_path = video_ref.replace("\\", "/").lstrip("/")
                video_object_key = normalize_video_object_key(rel_url_path)
                if not minio_object_exists(video_object_key):
                    raise RuntimeError("视频文件不存在")

                job_id = extract_job_id_from_object_key(video_object_key) or str(uuid.uuid4())
                video_url = minio_presigned_url(video_object_key)
                source_kind = "minio"
                source_ref = video_object_key

            # 所有产物都写到临时目录，分析结束后统一上传到 MinIO
            with tempfile.TemporaryDirectory(prefix="leader-out-") as temp_out:
                output_dir = os.path.join(temp_out, job_id)
                os.makedirs(output_dir, exist_ok=True)

                if parsed.scheme in ("http", "https"):
                    yield json.dumps({"status": "progress", "message": "正在下载视频以计算 md5..."}) + "\n"
                    url_ext = os.path.splitext(parsed.path or "")[1]
                    if not url_ext:
                        url_ext = ".mp4"
                    local_source = os.path.join(output_dir, f"source{url_ext}")
                    await asyncio.to_thread(_download_url_to_file, video_ref, local_source)
                    video_md5 = await asyncio.to_thread(_file_md5, local_source)
                    video_source = local_source
                else:
                    etag_md5 = minio_object_etag_md5(video_object_key)
                    if etag_md5:
                        video_md5 = etag_md5
                        video_source = minio_presigned_url(video_object_key)
                    else:
                        yield json.dumps({"status": "progress", "message": "正在下载视频以计算 md5..."}) + "\n"
                        local_source = os.path.join(output_dir, "source.mp4")
                        await asyncio.to_thread(minio_download_to_file, video_object_key, local_source)
                        video_md5 = await asyncio.to_thread(_file_md5, local_source)
                        video_source = local_source

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
                        seg["image_object_key"] = image_object_key
                        seg["image_url"] = minio_presigned_url(image_object_key)
                        report_content = report_content.replace(f"]({seg['image_path']})", f"]({seg['image_url']})")

                mysql_saved = False
                mysql_error = ""
                try:
                    from .mysql_store import _sanitize_config, save_artifact_by_md5

                    meta = {
                        "job_id": job_id,
                        "object_key": video_object_key,
                        "video_url": video_url,
                        "video_path": video_object_key or video_ref,
                        "config": _sanitize_config(config),
                    }
                    save_artifact_by_md5(
                        video_md5,
                        media_type=str(ai_analysis.get("media_type", "") or ""),
                        asset_type=str(ai_analysis.get("media_type", "") or ""),
                        source_kind=source_kind,
                        source_ref=source_ref or None,
                        meta=meta,
                        artifact_type="ai_analysis",
                        artifact_version=1,
                        content_json=ai_analysis,
                    )
                    save_artifact_by_md5(
                        video_md5,
                        media_type=str(ai_analysis.get("media_type", "") or ""),
                        asset_type=str(ai_analysis.get("media_type", "") or ""),
                        source_kind=source_kind,
                        source_ref=source_ref or None,
                        meta=meta,
                        artifact_type="report_markdown",
                        artifact_version=1,
                        content_text=report_content,
                    )
                    raw_transcript = ai_analysis.get("raw_transcript")
                    if raw_transcript:
                        save_artifact_by_md5(
                            video_md5,
                            media_type=str(ai_analysis.get("media_type", "") or ""),
                            asset_type=str(ai_analysis.get("media_type", "") or ""),
                            source_kind=source_kind,
                            source_ref=source_ref or None,
                            meta=meta,
                            artifact_type="raw_transcript",
                            artifact_version=1,
                            content_text=str(raw_transcript),
                        )
                        subtitle_lines: list[dict] = []
                        for ln in str(raw_transcript).splitlines():
                            m = re.match(r"^\[(\d+(?:\.\d+)?)s\]\s*(.*)$", ln.strip())
                            if not m:
                                continue
                            subtitle_lines.append({"timestamp": float(m.group(1)), "text": m.group(2)})
                        if subtitle_lines:
                            save_artifact_by_md5(
                        video_md5,
                        media_type=str(ai_analysis.get("media_type", "") or ""),
                        asset_type=str(ai_analysis.get("media_type", "") or ""),
                        source_kind=source_kind,
                        source_ref=source_ref or None,
                        meta=meta,
                        artifact_type="subtitle_lines",
                        artifact_version=1,
                        content_json={"lines": subtitle_lines},
                    )

                # Extract and save captured frames
                    captured_frames = []
                    for seg in ai_analysis.get("segments", []):
                        if "image_url" in seg:
                            captured_frames.append({
                                "url": seg["image_url"],
                                "timestamp": seg.get("timestamp", 0),
                                "object_key": seg.get("image_object_key", "")
                            })
                    
                    if captured_frames:
                        save_artifact_by_md5(
                            video_md5,
                            media_type=str(ai_analysis.get("media_type", "") or ""),
                            asset_type=str(ai_analysis.get("media_type", "") or ""),
                            source_kind=source_kind,
                            source_ref=source_ref or None,
                            meta=meta,
                            artifact_type="captured_frames",
                            artifact_version=1,
                            content_json=captured_frames,
                        )

                    mysql_saved = True
                except Exception as e:
                    mysql_error = str(e)

                yield json.dumps(
                    {
                        "status": "success",
                        "report": report_content,
                        "data": ai_analysis,
                        "video_url": video_url,
                        "video_path": video_object_key or video_ref,
                        "object_key": video_object_key,
                        "video_md5": video_md5,
                        "mysql_saved": mysql_saved,
                        "mysql_error": mysql_error,
                        "outputs_base_url": "minio",
                    }
                ) + "\n"
        except Exception as e:
            print(f"Error during analysis: {e}")
            yield json.dumps({"status": "error", "message": str(e)}) + "\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/analysis/by_md5/{video_md5}")
async def get_analysis_by_md5(video_md5: str):
    try:
        from .mysql_store import load_latest_by_md5

        data = load_latest_by_md5(video_md5)
        if not data:
            raise HTTPException(status_code=404, detail="未找到该 md5 的数据")
        asset = data.get("asset") or {}
        access_url = ""
        try:
            sk = (asset.get("source_kind") or "").strip().lower()
            sr = (asset.get("source_ref") or "").strip()
            if sk == "minio" and sr:
                access_url = minio_presigned_url(sr)
            elif sk == "url" and sr:
                access_url = sr
        except Exception:
            access_url = ""
        data["access"] = {"primary_url": access_url}

        # Refresh image URLs in artifacts
        artifacts = data.get("artifacts", {})
        
        # 1. ai_analysis
        ai_list = artifacts.get("ai_analysis", [])
        if ai_list:
            for item in ai_list:
                cj = item.get("json")
                meta = item.get("meta")
                if not isinstance(meta, dict):
                    meta = {}
                job_id = meta.get("job_id", "")
                
                if isinstance(cj, dict) and "segments" in cj and isinstance(cj["segments"], list):
                    for seg in cj["segments"]:
                        iok = seg.get("image_object_key")
                        if not iok and job_id and seg.get("image_path"):
                            iok = minio_object_key("outputs", job_id, seg["image_path"])
                            seg["image_object_key"] = iok
                        
                        if iok:
                            try:
                                seg["image_url"] = minio_presigned_url(iok)
                            except Exception:
                                pass
        
        # 2. captured_frames
        cf_list = artifacts.get("captured_frames", [])
        if cf_list:
            for item in cf_list:
                cj = item.get("json")
                if isinstance(cj, list):
                    for frame in cj:
                        iok = frame.get("object_key")
                        if iok:
                            try:
                                frame["url"] = minio_presigned_url(iok)
                            except Exception:
                                pass

        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/analysis/{video_md5}")
async def delete_analysis(video_md5: str):
    """
    删除指定 md5 的所有分析数据，包括：
    1. MySQL 中的 media_assets 和 media_artifacts
    2. MinIO 中的 outputs/{job_id} 目录
    3. MinIO 中的 uploads/{job_id} 目录 (如果 source_kind=minio)
    """
    try:
        from .mysql_store import load_latest_by_md5, delete_asset_by_md5
        
        # 1. Load data to get job_id and source info
        data = load_latest_by_md5(video_md5)
        if not data:
            return {"status": "success", "message": "Data not found, nothing to delete"}
            
        asset = data.get("asset") or {}
        artifacts = data.get("artifacts") or {}
        
        job_id = ""
        # Try to find job_id from meta in artifacts (any artifact will do)
        # Usually in ai_analysis meta
        ai_list = artifacts.get("ai_analysis", [])
        if ai_list:
             meta = ai_list[0].get("meta")
             if isinstance(meta, dict):
                 job_id = meta.get("job_id", "")
        
        # If not found in artifact meta, check asset meta if available (though schema usually stores it in artifact meta)
        # But wait, asset table has meta_json too.
        if not job_id:
            mj = asset.get("meta_json")
            if isinstance(mj, dict):
                job_id = mj.get("job_id", "")
        
        # 2. Delete from MinIO
        if job_id:
            # Delete outputs (analysis results)
            minio_remove_folder(minio_object_key("outputs", job_id))
            
            # Delete uploads if it was an upload
            # Check source_kind
            sk = (asset.get("source_kind") or "").strip().lower()
            if sk == "minio":
                 # source_ref usually is full key like "uploads/uuid/file.mp4"
                 sr = (asset.get("source_ref") or "").strip()
                 if sr:
                     # Remove the specific file
                     minio_remove_object(sr)
                     # Also try to remove the folder "uploads/{job_id}" if it's that structure
                     # extract_job_id_from_object_key helps check this
                     jid_from_key = extract_job_id_from_object_key(sr)
                     if jid_from_key == job_id:
                         minio_remove_folder(minio_object_key("uploads", job_id))

        # 3. Delete from MySQL
        delete_asset_by_md5(video_md5)
        
        return {"status": "success", "message": "Deleted successfully"}
        
    except Exception as e:
        print(f"Error deleting analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/analysis/list")
async def list_analyses(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    try:
        from .mysql_store import list_assets_with_artifact

        items = list_assets_with_artifact(artifact_type="ai_analysis", limit=limit, offset=offset)
        for it in items:
            sk = (it.get("source_kind") or "").strip().lower()
            sr = (it.get("source_ref") or "").strip()
            access_url = ""
            try:
                if sk == "minio" and sr:
                    access_url = minio_presigned_url(sr)
                elif sk == "url" and sr:
                    access_url = sr
            except Exception:
                access_url = ""
            it["access"] = {"primary_url": access_url}
            if not it.get("display_name") and sr:
                it["display_name"] = os.path.basename(sr.replace("\\", "/"))

            # Refresh image URLs in content_json (cover images)
            cj = it.get("content_json")
            if isinstance(cj, dict) and "segments" in cj and isinstance(cj["segments"], list):
                job_id = ""
                meta = it.get("meta")
                if isinstance(meta, dict):
                    job_id = meta.get("job_id", "")
                
                for seg in cj["segments"]:
                    # Try to get object key
                    iok = seg.get("image_object_key")
                    if not iok and job_id and seg.get("image_path"):
                        # Fallback: construct object key if missing but job_id is known
                        iok = minio_object_key("outputs", job_id, seg["image_path"])
                        seg["image_object_key"] = iok 
                    
                    if iok:
                        try:
                            # Generate fresh presigned URL
                            seg["image_url"] = minio_presigned_url(iok)
                        except Exception:
                            pass

        return {"items": items, "limit": limit, "offset": offset}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
