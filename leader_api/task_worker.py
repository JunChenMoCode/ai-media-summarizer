import asyncio
import logging
import traceback
import json
import os
import tempfile
import uuid
from urllib.parse import urlparse
import shutil
from .task_store import tasks, queue, TaskStatus
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
    minio_remove_folder,
)
from .models import AnalyzePathRequest, ConfigModel
from fast_video_summary import FastVideoAnalyzer
from .mysql_store import save_artifact_by_md5

# Re-use the md5 and download logic from analyze.py
# Ideally this should be in a shared utility module
import hashlib
import urllib.request
try:
    import yt_dlp
except ImportError:
    yt_dlp = None

def _file_md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def _download_url_to_file(url: str, path: str) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp, open(path, "wb") as out:
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)

def _download_video_smart(url: str, output_path: str, progress_callback=None) -> str:
    """
    Download video using yt-dlp if available and appropriate, otherwise direct download.
    Returns the actual path of the downloaded file.
    """
    use_ytdlp = False
    if yt_dlp:
        # Check for common video sites
        if any(x in url for x in ["bilibili.com", "youtube.com", "youtu.be", "vimeo.com"]):
            use_ytdlp = True
            
    if use_ytdlp:
        # Use yt-dlp
        base_path = os.path.splitext(output_path)[0]
        
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': base_path + '.%(ext)s',
            'quiet': True,
            'no_warnings': True,
        }
        
        if progress_callback:
            def hook(d):
                if d['status'] == 'downloading':
                    try:
                        p = d.get('_percent_str', '0%').replace('%','')
                        progress_callback(float(p))
                    except:
                        pass
            ydl_opts['progress_hooks'] = [hook]

        try:
            print(f"Attempting yt-dlp download for: {url}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if 'entries' in info:
                    info = info['entries'][0]
                
                ext = info.get('ext', 'mp4')
                final_path = f"{base_path}.{ext}"
                
                # Check likely candidates if exact match missing
                if not os.path.exists(final_path):
                    import glob
                    candidates = glob.glob(f"{base_path}.*")
                    if candidates:
                        final_path = candidates[0]
                
                if os.path.exists(final_path):
                    return final_path
        except Exception as e:
            print(f"yt-dlp download failed: {e}, falling back to direct download")

    # Direct download
    _download_url_to_file(url, output_path)
    return output_path

async def worker_loop():
    print("Background worker started.")
    while True:
        try:
            task_id = await queue.get()
            task = tasks.get(task_id)
            
            if not task or task.status == TaskStatus.CANCELLED:
                queue.task_done()
                continue
                
            if task.status != TaskStatus.PENDING:
                queue.task_done()
                continue

            print(f"Starting task {task_id} for URL: {task.url}")
            task.status = TaskStatus.RUNNING
            task.progress = 5
            task.logs.append("Task started.")
            
            try:
                await process_video_task(task)
                if task.status != TaskStatus.CANCELLED:
                    task.status = TaskStatus.COMPLETED
                    task.progress = 100
                    task.logs.append("Task completed successfully.")
            except Exception as e:
                print(f"Task {task_id} failed: {e}")
                traceback.print_exc()
                task.status = TaskStatus.FAILED
                task.error = str(e)
                task.logs.append(f"Error: {str(e)}")
            finally:
                queue.task_done()
                
        except asyncio.CancelledError:
            print("Worker cancelled.")
            break
        except Exception as e:
            print(f"Worker error: {e}")
            await asyncio.sleep(1)

async def process_video_task(task):
    # This is a simplified version of analyze_video_by_path adapted for background execution
    video_ref = task.url
    
    # Create default config
    config = ConfigModel(
        openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
        openai_base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        llm_model=os.environ.get("LLM_MODEL", "gpt-3.5-turbo"),
        model_size="base",
        device="cpu",
        compute_type="int8",
        capture_offset=0.5
    )
    
    task.logs.append("Initializing analysis...")
    
    parsed = urlparse(video_ref)
    job_id = ""
    video_source = ""
    video_md5 = ""
    
    # Setup job context
    if parsed.scheme in ("http", "https"):
        job_id = str(uuid.uuid4())
    else:
        # MinIO path support (if needed)
        job_id = str(uuid.uuid4())

    # Use persistent directory instead of temporary one to ensure artifacts (video, images) survive
    # fast_output is mounted as /static in app.py
    # If MinIO is enabled, we can use a temporary directory because artifacts will be uploaded to MinIO.
    use_minio = minio_enabled()
    
    if use_minio:
        # Use a temporary directory context managed manually or just create one and cleanup later
        # Since this function is async and we want to keep structure simple:
        temp_dir_obj = tempfile.TemporaryDirectory(prefix="leader-task-")
        base_output_dir = temp_dir_obj.name
        # We don't need "tasks" subdir really, but to keep structure similar:
        output_dir = os.path.join(base_output_dir, job_id)
        os.makedirs(output_dir, exist_ok=True)
    else:
        temp_dir_obj = None
        base_output_dir = os.path.join(os.getcwd(), "fast_output", "tasks")
        os.makedirs(base_output_dir, exist_ok=True)
        output_dir = os.path.join(base_output_dir, job_id)
        os.makedirs(output_dir, exist_ok=True)
    
    try:
        # Download
        task.logs.append("Downloading video...")
        local_source_target = os.path.join(output_dir, "source.mp4")
        
        def download_progress(p):
            # p is 0-100 float
            # Map 0-100 download to task progress 5-15
            try:
                task.progress = 5 + int(float(p) * 0.1)
            except:
                pass
        
        try:
            local_source = await asyncio.to_thread(_download_video_smart, video_ref, local_source_target, download_progress)
        except Exception as e:
            raise RuntimeError(f"Failed to download video: {e}")
            
        task.progress = 15
        
        # MD5
        task.logs.append("Calculating MD5...")
        if not os.path.exists(local_source):
             raise RuntimeError(f"Video file not found at {local_source}")
             
        video_md5 = await asyncio.to_thread(_file_md5, local_source)
        video_source = local_source
        task.progress = 20
        
        # Analyze
        task.logs.append("Starting analysis model...")
        
        def progress_cb(msg):
            task.logs.append(msg)
            # Rough mapping of messages to progress
            if "Transcribing" in msg or "转录" in msg:
                task.progress = 30
            elif "LLM" in msg:
                task.progress = 60
            elif "Summary" in msg or "摘要" in msg:
                task.progress = 80
            elif "Report" in msg or "报告" in msg:
                task.progress = 90
        
        analyzer = FastVideoAnalyzer(
            video_source,
            output_dir,
            config=config.model_dump(),
            progress_callback=progress_cb,
        )
        
        ai_analysis = await asyncio.to_thread(analyzer.run)
        
        if not ai_analysis:
            raise RuntimeError("Analysis returned no results")
            
        task.logs.append("Uploading results...")
        
        # Upload to MinIO (Optional)
        if use_minio:
            minio_upload_tree(output_dir, minio_object_key("outputs", job_id))
        
        # Read report
        report_path = os.path.join(output_dir, "final_report.md")
        report_content = ""
        if os.path.exists(report_path):
            with open(report_path, "r", encoding="utf-8") as f:
                report_content = f.read()

        # Fix image links
        # If MinIO enabled, use MinIO URLs (relative/object_key). Otherwise use local static URLs.
        
        for seg in ai_analysis.get("segments", []):
            if "image_path" in seg:
                # image_path from analyzer is relative to output_dir, e.g., "images/keyframe_00_12s.jpg"
                # We need to ensure it is correct.
                
                # Normalize path separators
                rel_path = seg["image_path"].replace("\\", "/")
                
                if use_minio:
                    image_object_key = minio_object_key("outputs", job_id, rel_path)
                    seg["image_object_key"] = image_object_key
                    # Do NOT bake in presigned URL to report or analysis to avoid expiration
                    # Leave image_url as relative path or empty, analyze.py will generate it
                    seg["image_url"] = rel_path 
                    # Do NOT replace in report_content if using MinIO, analyze.py will handle relative paths
                else:
                    # Use local static URL
                    # /static/tasks/<job_id>/<rel_path>
                    # Assuming app mounts fast_output as /static
                    seg["image_url"] = f"/static/tasks/{job_id}/{rel_path}"
                    report_content = report_content.replace(f"]({seg['image_path']})", f"]({seg['image_url']})")
        
        # Save to MySQL
        task.logs.append("Saving to database...")
        meta = {
            "config": config.model_dump(),
            "original_filename": os.path.basename(parsed.path) or "video.mp4",
            "job_id": job_id
        }
        
        # Determine video source ref for database
        if use_minio:
            saved_source_kind = "minio"
            saved_source_ref = minio_object_key("outputs", job_id, "source.mp4")
        else:
            saved_source_kind = "local"
            saved_source_ref = f"tasks/{job_id}/source.mp4"
        
        # If original was URL, maybe keep it? But we want to play the downloaded file.
        # The frontend Video.vue or AiVideoSummary.vue expects to play something.
        
        await asyncio.to_thread(save_artifact_by_md5,
            video_md5=video_md5,
            media_type="video",
            asset_type="video",
            mime_type="video/mp4",
            display_name=meta["original_filename"],
            source_kind=saved_source_kind,
            source_ref=saved_source_ref,
            meta=meta,
            artifact_type="ai_analysis",
            content_json=ai_analysis
        )
        
        # Save report
        await asyncio.to_thread(save_artifact_by_md5,
            video_md5=video_md5,
            # Do not overwrite asset-level properties with report details
            # media_type="text",
            # asset_type="report_markdown",
            # mime_type="text/markdown", 
            # display_name="Final Report",
            # source_kind="generated",
            # source_ref=f"tasks/{job_id}/final_report.md",
            meta=meta, # Keep/Update asset meta with job_id
            artifact_type="report_markdown",
            content_text=report_content,
            artifact_meta=meta # Also store meta in artifact
        )

        # Extract and save captured frames
        captured_frames = []
        for seg in ai_analysis.get("segments", []):
            if "image_path" in seg:
                captured_frames.append({
                    "url": seg.get("image_url", ""),
                    "timestamp": seg.get("timestamp", 0),
                    "object_key": seg.get("image_object_key", "")
                })
        
        if captured_frames:
            await asyncio.to_thread(save_artifact_by_md5,
                video_md5=video_md5,
                media_type="video",
                asset_type="video",
                source_kind=saved_source_kind,
                source_ref=saved_source_ref,
                meta=meta,
                artifact_type="captured_frames",
                content_json=captured_frames
            )
        
        task.result = {
            "md5": video_md5,
            "job_id": job_id
        }
    except Exception as e:
        task.logs.append(f"Processing error: {str(e)}")
        raise e
    finally:
        # Cleanup if using temp dir
        if temp_dir_obj:
            try:
                temp_dir_obj.cleanup()
            except:
                pass
