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
from .mysql_store import load_app_config

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
            config = load_app_config()
            if not config:
                raise RuntimeError("数据库配置为空，请先在前端设置并保存")
            print(f">>> [DEBUG] analyze_path config: {config}")
            # Ensure empty strings in config are None so FastVideoAnalyzer can handle defaults correctly?
            # No, FastVideoAnalyzer logic is: if v is not None and str(v).strip(): self.config[k] = v
            # So if we pass "", it won't override. But if we pass "sk-...", it will.
            
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
                    selected_images=request.selected_images
                )
                task = asyncio.create_task(asyncio.to_thread(analyzer.run))

                while not task.done() or not queue.empty():
                    try:
                        msg = await asyncio.wait_for(queue.get(), timeout=0.5)
                        yield json.dumps({"status": "progress", "message": msg}) + "\n"
                    except asyncio.TimeoutError:
                        continue

                ai_analysis = task.result()

                # Override title if user prefers filename
                if ai_analysis and config.get("title_preference") == "filename":
                    original_name = ""
                    # 1. Try to get filename from MinIO object key
                    if video_object_key:
                        original_name = os.path.basename(video_object_key)
                        # Handle potential URL encoding or "uploads/uuid/filename"
                        # But normalize_video_object_key might have kept it clean?
                        # Usually it is clean enough.
                    # 2. Try to get filename from URL
                    elif video_url:
                        try:
                            path = urlparse(video_url).path
                            original_name = os.path.basename(path)
                            from urllib.parse import unquote
                            original_name = unquote(original_name)
                        except:
                            pass
                    
                    if original_name and isinstance(ai_analysis, dict):
                        ai_analysis["title"] = original_name

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

                no_subtitles = ai_analysis.get("no_subtitles", False)
                report_content = ""

                yield json.dumps({"status": "progress", "message": "正在上传分析产物到 MinIO..."}) + "\n"
                minio_upload_tree(output_dir, minio_object_key("outputs", job_id))

                if not no_subtitles:
                    report_path = os.path.join(output_dir, "final_report.md")
                    if os.path.exists(report_path):
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
            elif sk == "local" and sr:
                 # Assume local static file
                 if sr.startswith("/static/") or sr.startswith("static/"):
                     access_url = f"/{sr.lstrip('/')}"
                 else:
                     access_url = f"/static/{sr}"
        except Exception:
            access_url = ""
        data["access"] = {"primary_url": access_url}

        # Refresh image URLs in artifacts
        artifacts = data.get("artifacts", {})
        
        # 1. ai_analysis
        ai_list = artifacts.get("ai_analysis", [])
        fallback_title = (
            (asset.get("display_name") or "").strip()
            or os.path.basename((asset.get("source_ref") or "").replace("\\", "/"))
            or (asset.get("md5") or "").strip()
            or video_md5
        )
        
        # Helper to get job_id from asset if missing in artifact
        asset_meta = asset.get("meta_json")
        if not isinstance(asset_meta, dict):
            asset_meta = {}
        asset_job_id = asset_meta.get("job_id", "")
        
        # Fallback: try to extract job_id from source_ref if local
        if not asset_job_id and asset.get("source_kind") == "local":
             sr = asset.get("source_ref") or ""
             # format: tasks/{job_id}/...
             if sr.startswith("tasks/"):
                 parts = sr.split("/")
                 if len(parts) >= 2:
                     asset_job_id = parts[1]

        if ai_list:
            for item in ai_list:
                cj = item.get("json")
                meta = item.get("meta")
                if not isinstance(meta, dict):
                    meta = {}
                job_id = meta.get("job_id", "")
                if not job_id:
                    job_id = asset_job_id
                
                # Check if this is a local asset
                is_local = False
                if asset.get("source_kind") == "local":
                    is_local = True

                if isinstance(cj, dict) and not str(cj.get("title") or "").strip():
                    cj["title"] = fallback_title

                if isinstance(cj, dict) and "segments" in cj and isinstance(cj["segments"], list):
                    for seg in cj["segments"]:
                        if is_local:
                             # For local assets, ensure image_url points to static
                             if job_id and seg.get("image_path") and not seg.get("image_url", "").startswith("/static/"):
                                 # Re-construct static URL if missing or invalid
                                 rel_path = seg["image_path"].replace("\\", "/")
                                 seg["image_url"] = f"/static/tasks/{job_id}/{rel_path}"
                             continue

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
                meta = item.get("meta")
                if not isinstance(meta, dict):
                    meta = {}
                job_id = meta.get("job_id", "")
                if not job_id:
                    job_id = asset_job_id
                
                # Check if this is a local asset
                is_local = False
                if asset.get("source_kind") == "local":
                    is_local = True

                if isinstance(cj, list):
                    for frame in cj:
                        if is_local:
                             if frame.get("url") and not frame.get("url", "").startswith("/static/"):
                                  # Try to fix using object_key
                                  # object_key format: outputs/{job_id}/{rel_path}
                                  # We want: /static/tasks/{job_id}/{rel_path}
                                  ok = frame.get("object_key")
                                  if ok and job_id:
                                      # Remove prefix "outputs/{job_id}/"
                                      prefix = f"outputs/{job_id}/"
                                      if ok.startswith(prefix):
                                          rel = ok[len(prefix):]
                                          frame["url"] = f"/static/tasks/{job_id}/{rel}"
                                      elif ok.startswith("outputs/"): # Fallback if job_id mismatch or not present in key
                                          parts = ok.split("/")
                                          if len(parts) >= 3: # outputs, job_id, ...
                                              # Assuming structure outputs/job_id/...
                                              # Local structure: tasks/job_id/...
                                              # /static/tasks/job_id/...
                                              # So just replace "outputs" with "tasks" and prepend "/static/"?
                                              # Wait, local dir is fast_output/tasks.
                                              # Static mount is /static -> fast_output.
                                              # So /static/tasks/...
                                              # If object_key is outputs/jid/file, we want tasks/jid/file.
                                              # So replace first "outputs" with "tasks".
                                              new_path = ok.replace("outputs/", "tasks/", 1)
                                              frame["url"] = f"/static/{new_path}"
                             continue

                        iok = frame.get("object_key")
                        if iok:
                            try:
                                frame["url"] = minio_presigned_url(iok)
                            except Exception:
                                pass

        # 3. report_markdown (Refresh image links)
        report_list = artifacts.get("report_markdown", [])
        if report_list:
            for item in report_list:
                content_text = item.get("text") or ""
                # Try to get job_id
                meta = item.get("meta")
                if not isinstance(meta, dict):
                    meta = {}
                job_id = meta.get("job_id", "")
                if not job_id:
                    job_id = asset_job_id
                
                if job_id and content_text:
                    def replace_link(match):
                        alt = match.group(1)
                        url = match.group(2)
                        # Check if relative (not http/blob/data/slash)
                        if not url or url.startswith("http") or url.startswith("/") or url.startswith("data:") or url.startswith("blob:"):
                            return match.group(0)
                        
                        # If local, task_worker already replaced it with /static/, so we shouldn't be here typically.
                        # But if somehow we are, handled by startswith("/") check above? 
                        # Wait, task_worker replaced it with /static/... which starts with /.
                        # So for local files, we skip.
                        
                        # For MinIO, task_worker left it relative.
                        if minio_enabled():
                             try:
                                 # Normalize path
                                 rel = url.replace("\\", "/")
                                 # object key: outputs/{job_id}/{rel}
                                 key = minio_object_key("outputs", job_id, rel)
                                 signed = minio_presigned_url(key)
                                 return f"![{alt}]({signed})"
                             except:
                                 pass
                        return match.group(0)

                    new_text = re.sub(r'!\[(.*?)\]\((.*?)\)', replace_link, content_text)
                    item["text"] = new_text

        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e





@router.get("/analysis/tags")
async def get_all_tags():
    """
    Get aggregated tags from all analysis results for word cloud.
    Returns: {"tags": [{"name": "tag1", "value": 10}, ...]}
    """
    try:
        from .mysql_store import get_all_analysis_tags
        tags = get_all_analysis_tags()
        return {"status": "success", "tags": tags}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
@router.get("/analysis/list")
async def list_analyses(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    folder_id: str | None = Query(None),
):
    try:
        from .mysql_store import list_assets_with_artifact

        items = list_assets_with_artifact(
            artifact_type="ai_analysis", 
            limit=limit, 
            offset=offset,
            folder_id=folder_id
        )
        for it in items:
            sk = (it.get("source_kind") or "").strip().lower()
            sr = (it.get("source_ref") or "").strip()
            access_url = ""
            try:
                if sk == "minio" and sr:
                    access_url = minio_presigned_url(sr)
                elif sk == "url" and sr:
                    access_url = sr
                elif sk == "local" and sr:
                    access_url = f"/static/{sr}"
            except Exception:
                access_url = ""
            it["access"] = {"primary_url": access_url}
            if not it.get("display_name") and sr:
                it["display_name"] = os.path.basename(sr.replace("\\", "/"))

            cj = it.get("content_json")
            fallback_title = (
                (it.get("display_name") or "").strip()
                or os.path.basename(sr.replace("\\", "/"))
                or (it.get("md5") or "").strip()
            )
            if isinstance(cj, dict) and not str(cj.get("title") or "").strip():
                cj["title"] = fallback_title

            # Refresh image URLs in content_json (cover images)
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


@router.post("/analysis/{video_md5}/read")
async def mark_analysis_read(video_md5: str):
    """
    Mark an analysis as read.
    """
    print(f"Marking analysis {video_md5} as read...")
    try:
        from .mysql_store import mark_asset_as_read
        
        success = mark_asset_as_read(video_md5)
        print(f"Mark read result for {video_md5}: {success}")
        return {"status": "success", "updated": success}
    except Exception as e:
        print(f"Error marking read: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
