import os
import shutil
import uuid
import json
import asyncio
import torch
import re
import subprocess
import mimetypes
from datetime import timedelta
from urllib.parse import urlparse, unquote
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, WebSocket
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from fast_video_summary import FastVideoAnalyzer
from openai import OpenAI, AsyncOpenAI, BadRequestError
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, AutoProcessor, AutoModelForCausalLM

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

try:
    proxy = (os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY") or os.getenv("ALL_PROXY") or "").strip()
    if not proxy:
        proxy = (os.getenv("YTDLP_PROXY") or os.getenv("YT_DLP_PROXY") or "").strip()
    if proxy and "://" not in proxy:
        proxy = "http://" + proxy
    if proxy:
        os.environ.setdefault("HTTP_PROXY", proxy)
        os.environ.setdefault("HTTPS_PROXY", proxy)
        os.environ.setdefault("ALL_PROXY", proxy)
        os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
except Exception:
    pass

app = FastAPI()

# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "web_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
OUTPUTS_DIR = "fast_output"
os.makedirs(OUTPUTS_DIR, exist_ok=True)

# 挂载静态文件目录，用于访问生成的报告和图片
app.mount("/outputs", StaticFiles(directory=OUTPUTS_DIR), name="outputs")
app.mount("/uploads", StaticFiles(directory="web_uploads"), name="uploads")

try:
    from minio import Minio
except Exception:
    Minio = None

try:
    import yt_dlp
except Exception:
    yt_dlp = None

_MINIO_CLIENT = None

def _minio_enabled() -> bool:
    return bool(os.getenv("MINIO_ENDPOINT", "").strip())

def _minio_bucket() -> str:
    return os.getenv("MINIO_BUCKET", "leader").strip() or "leader"

def _minio_secure() -> bool:
    v = (os.getenv("MINIO_SECURE", "") or "").strip().lower()
    return v in ("1", "true", "yes", "y")

def _minio_public_base_url() -> str:
    v = (os.getenv("MINIO_PUBLIC_BASE_URL", "") or "").strip().rstrip("/")
    if v:
        return v
    endpoint = (os.getenv("MINIO_ENDPOINT", "") or "").strip()
    scheme = "https" if _minio_secure() else "http"
    return f"{scheme}://{endpoint}".rstrip("/")

def _minio_get_client():
    global _MINIO_CLIENT
    if _MINIO_CLIENT is not None:
        return _MINIO_CLIENT
    if not _minio_enabled():
        raise RuntimeError("MinIO 未启用")
    if Minio is None:
        raise RuntimeError("缺少 minio 依赖，请先 pip install minio")

    endpoint = (os.getenv("MINIO_ENDPOINT", "") or "").strip()
    access_key = (os.getenv("MINIO_ACCESS_KEY", "") or "").strip()
    secret_key = (os.getenv("MINIO_SECRET_KEY", "") or "").strip()
    if not endpoint or not access_key or not secret_key:
        raise RuntimeError("MinIO 配置不完整，请设置 MINIO_ENDPOINT/MINIO_ACCESS_KEY/MINIO_SECRET_KEY")

    _MINIO_CLIENT = Minio(
        endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=_minio_secure(),
    )
    return _MINIO_CLIENT

def _minio_ensure_bucket() -> None:
    client = _minio_get_client()
    bucket = _minio_bucket()
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)

def _guess_content_type(path: str) -> str:
    t, _ = mimetypes.guess_type(path)
    return t or "application/octet-stream"

def _minio_object_key(*parts: str) -> str:
    return "/".join([str(p).strip("/").replace("\\", "/") for p in parts if p is not None and str(p) != ""])

def _minio_public_url(object_key: str) -> str:
    base = _minio_public_base_url()
    bucket = _minio_bucket()
    return f"{base}/{bucket}/{object_key.lstrip('/')}"

def _minio_presigned_url(object_key: str, days: int = 7) -> str:
    _minio_ensure_bucket()
    client = _minio_get_client()
    bucket = _minio_bucket()
    return client.presigned_get_object(bucket, object_key, expires=timedelta(days=days))

def _minio_upload_file(local_path: str, object_key: str, content_type: str | None = None) -> str:
    _minio_ensure_bucket()
    client = _minio_get_client()
    bucket = _minio_bucket()
    ct = content_type or _guess_content_type(local_path)
    client.fput_object(bucket, object_key, local_path, content_type=ct)
    return _minio_presigned_url(object_key)

def _minio_upload_tree(local_dir: str, object_prefix: str) -> None:
    prefix = _minio_object_key(object_prefix)
    for root, _, files in os.walk(local_dir):
        for fn in files:
            local_path = os.path.join(root, fn)
            rel = os.path.relpath(local_path, local_dir).replace(os.sep, "/")
            object_key = _minio_object_key(prefix, rel)
            _minio_upload_file(local_path, object_key)

class ConfigModel(BaseModel):
    openai_api_key: str
    openai_base_url: str
    llm_model: str
    vl_model: str = "Pro/Qwen/Qwen2-VL-7B-Instruct"
    vl_base_url: str = "https://api.siliconflow.cn/v1"
    vl_api_key: str = ""
    model_size: str
    device: str
    compute_type: str
    capture_offset: float

class TranscriptLine(BaseModel):
    timestamp: float
    text: str

class TranslateRequest(BaseModel):
    lines: list[TranscriptLine]
    config: ConfigModel

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    transcript: str | None = None
    summary: str | None = None
    config: ConfigModel

class MindMapRequest(BaseModel):
    transcript: str
    config: ConfigModel

class NotesRequest(BaseModel):
    transcript: str
    config: ConfigModel


_TRANSLATORS: dict[str, tuple] = {}
_OCR_VLM = None
_OCR_VLM_META = {}

def _guess_translate_source_lang(lines: list["TranscriptLine"]) -> str:
    texts = [getattr(line, "text", "") or "" for line in (lines or [])]
    if not texts:
        return "zh"
    cjk = 0
    latin = 0
    for t in texts[:200]:
        cjk += len(re.findall(r"[\u4e00-\u9fff]", t))
        latin += len(re.findall(r"[A-Za-z]", t))
    if cjk >= latin:
        return "zh"
    return "en"

def get_translator(device_pref: str, model_name: str):
    global _TRANSLATORS
    use_cuda = device_pref == "cuda" and torch.cuda.is_available()
    device = "cuda" if use_cuda else "cpu"
    key = f"{model_name}:{device}"
    if key in _TRANSLATORS:
        return _TRANSLATORS[key]
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
    model.to(device)
    model.eval()
    _TRANSLATORS[key] = (tokenizer, model, device)
    return _TRANSLATORS[key]

def translate_lines(lines: list[TranscriptLine], device_pref: str):
    source_lang = _guess_translate_source_lang(lines)
    if source_lang == "en":
        model_name = os.getenv("TRANSLATE_MODEL_EN_ZH", "Helsinki-NLP/opus-mt-en-zh")
    else:
        model_name = os.getenv("TRANSLATE_MODEL_ZH_EN", os.getenv("TRANSLATE_MODEL", "Helsinki-NLP/opus-mt-zh-en"))
    tokenizer, model, device = get_translator(device_pref, model_name)
    texts = [line.text for line in lines]
    batch_size = int(os.getenv("TRANSLATE_BATCH_SIZE", "16"))
    results = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        inputs = tokenizer(batch, return_tensors="pt", padding=True, truncation=True)
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            outputs = model.generate(**inputs, max_new_tokens=256)
        decoded = tokenizer.batch_decode(outputs, skip_special_tokens=True)
        results.extend(decoded)
    return results

import base64

def _encode_image_to_base64(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

import mimetypes

def analyze_image_with_vl_model(config: ConfigModel, image_path: str, prompt: str = "OCR:"):
    # Use VL specific config if available, otherwise fallback to LLM config
    api_key = config.vl_api_key if config.vl_api_key else config.openai_api_key
    base_url = config.vl_base_url if config.vl_base_url else config.openai_base_url
    model = config.vl_model
    
    if not api_key:
        raise ValueError("API Key is required for VL model")
        
    client = OpenAI(api_key=api_key, base_url=base_url)
    
    base64_image = _encode_image_to_base64(image_path)
    
    # Determine mime type based on file extension
    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type or not mime_type.startswith('image'):
        mime_type = 'image/jpeg' # Default fallback
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{base64_image}"
                        }
                    },
                    {"type": "text", "text": prompt}
                ]
            }
        ]
    )
    return response.choices[0].message.content

def analyze_image_with_vl_model_bytes(config: ConfigModel, image_bytes: bytes, mime_type: str, prompt: str = "OCR:"):
    api_key = config.vl_api_key if config.vl_api_key else config.openai_api_key
    base_url = config.vl_base_url if config.vl_base_url else config.openai_base_url
    model = config.vl_model
    
    if not api_key:
        raise ValueError("API Key is required for VL model")
        
    client = OpenAI(api_key=api_key, base_url=base_url)
    
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    mime_type = (mime_type or "").strip().lower()
    if not mime_type.startswith("image/"):
        mime_type = "image/jpeg"
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{base64_image}"
                        }
                    },
                    {"type": "text", "text": prompt}
                ]
            }
        ]
    )
    return response.choices[0].message.content

from urllib.request import Request, urlopen

def _download_image_bytes(url: str) -> tuple[bytes, str]:
    timeout_s = float(os.getenv("OCR_IMAGE_DOWNLOAD_TIMEOUT", "20"))
    max_bytes = int(os.getenv("OCR_MAX_IMAGE_BYTES", str(8 * 1024 * 1024)))
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=timeout_s) as resp:
        content_type = (resp.headers.get("Content-Type") or "").strip()
        buf = bytearray()
        while True:
            chunk = resp.read(64 * 1024)
            if not chunk:
                break
            buf.extend(chunk)
            if len(buf) > max_bytes:
                raise RuntimeError(f"图片过大: {len(buf)} bytes")
        if not buf:
            raise RuntimeError("图片下载为空")
        return bytes(buf), content_type

def _local_path_from_url(url: str):
    u = (url or "").strip()
    if not u:
        raise RuntimeError("空图片 URL")
    if os.path.isfile(u):
        return u
    parsed = urlparse(u)
    path = unquote(parsed.path or "")
    idx = path.find("/outputs/")
    if idx >= 0:
        rel = path[idx + len("/outputs/"):]
        rel = rel.lstrip("/").replace("/", os.sep)
        return os.path.join("fast_output", rel)
    if parsed.scheme in ("http", "https"):
        return None
    raise RuntimeError(f"不支持的图片 URL: {url}")


class CoursewareOcrItem(BaseModel):
    url: str
    timestamp: float
    name: str

class CoursewareOcrRequest(BaseModel):
    items: list[CoursewareOcrItem]
    config: ConfigModel

class ImportVideoUrlRequest(BaseModel):
    url: str

class AnalyzePathRequest(BaseModel):
    video_path: str
    config: ConfigModel

def _safe_join(base_dir: str, rel_path: str) -> str:
    rel = (rel_path or "").replace("\\", "/").lstrip("/")
    parts = [p for p in rel.split("/") if p]
    if any(p == ".." for p in parts):
        raise RuntimeError("非法路径")
    return os.path.join(base_dir, *parts)

def _sanitize_filename(name: str) -> str:
    base = re.sub(r"[^\w\u4e00-\u9fff\-\.\s]+", "_", (name or "").strip())
    base = re.sub(r"\s+", " ", base).strip()
    if not base:
        base = "video"
    if len(base) > 80:
        base = base[:80].strip()
    if not base.lower().endswith(".mp4"):
        base += ".mp4"
    return base

def _normalize_proxy_url(proxy: str) -> str:
    p = (proxy or "").strip()
    if not p:
        return ""
    if "://" in p:
        return p
    return "http://" + p

def _guess_platform_from_url(url: str) -> str:
    u = (url or "").strip()
    try:
        host = (urlparse(u).netloc or "").lower()
    except Exception:
        host = ""
    if not host:
        return ""
    if "youtu.be" in host or "youtube.com" in host:
        return "youtube"
    if "b23.tv" in host or "bilibili.com" in host:
        return "bilibili"
    if "douyin.com" in host or "iesdouyin.com" in host:
        return "douyin"
    return host

def _yt_dlp_download(url: str, job_dir: str) -> tuple[str, str]:
    if yt_dlp is None:
        raise RuntimeError("缺少 yt-dlp 依赖，请先 pip install yt-dlp")

    os.makedirs(job_dir, exist_ok=True)
    before = set()
    try:
        before = set(os.listdir(job_dir))
    except Exception:
        before = set()

    outtmpl = os.path.join(job_dir, "download.%(ext)s")
    proxy = _normalize_proxy_url(os.getenv("YTDLP_PROXY", "") or os.getenv("YT_DLP_PROXY", ""))
    def _env_int(name: str, default: int) -> int:
        v = (os.getenv(name, "") or "").strip()
        if not v:
            return default
        try:
            return int(v)
        except Exception:
            return default
    def _env_bool(name: str, default: bool = False) -> bool:
        v = (os.getenv(name, "") or "").strip().lower()
        if not v:
            return default
        return v in ("1", "true", "yes", "y", "on")
    ydl_opts = {
        "format": "bestvideo+bestaudio/best",
        "outtmpl": outtmpl,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
        "windowsfilenames": True,
        "socket_timeout": _env_int("YTDLP_SOCKET_TIMEOUT", 30),
        "retries": _env_int("YTDLP_RETRIES", 10),
        "fragment_retries": _env_int("YTDLP_FRAGMENT_RETRIES", 10),
    }
    if proxy:
        ydl_opts["proxy"] = proxy
    if _env_bool("YTDLP_FORCE_IPV4", False):
        ydl_opts["force_ipv4"] = True
    impersonate = (os.getenv("YTDLP_IMPERSONATE", "") or "").strip()
    if impersonate:
        ydl_opts["impersonate"] = impersonate

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    title = ""
    if isinstance(info, dict):
        title = str(info.get("title") or "").strip()

    after = set()
    try:
        after = set(os.listdir(job_dir))
    except Exception:
        after = set()

    created = [fn for fn in (after - before) if fn and not fn.endswith((".part", ".ytdl", ".tmp"))]
    candidates = [os.path.join(job_dir, fn) for fn in created if os.path.isfile(os.path.join(job_dir, fn))]
    if not candidates:
        for ext in ("mp4", "mkv", "webm", "mov", "flv"):
            p = os.path.join(job_dir, f"download.{ext}")
            if os.path.isfile(p):
                candidates.append(p)

    if not candidates:
        raise RuntimeError("yt-dlp 下载失败：未找到输出文件")

    mp4s = [p for p in candidates if p.lower().endswith(".mp4")]
    pick = mp4s[0] if mp4s else max(candidates, key=lambda p: os.path.getsize(p) if os.path.exists(p) else 0)
    return pick, (title or "video")

def _import_video_from_url(url: str) -> dict:
    job_id = str(uuid.uuid4())
    job_dir = os.path.join(UPLOAD_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)
    source_url = url
    platform = _guess_platform_from_url(url)
    try:
        downloaded_path, yt_title = _yt_dlp_download(url, job_dir)
        title = yt_title
        filename = _sanitize_filename(title)
        output_path = os.path.join(job_dir, filename)
        if os.path.abspath(downloaded_path) != os.path.abspath(output_path):
            os.replace(downloaded_path, output_path)
    except Exception as e:
        proxy = _normalize_proxy_url(os.getenv("YTDLP_PROXY", "") or os.getenv("YT_DLP_PROXY", ""))
        hint = ""
        if platform == "youtube" and not proxy:
            hint = "（YouTube 可能需要代理，可在 .env 配置 YTDLP_PROXY=http://127.0.0.1:7897）"
        raise RuntimeError(f"yt-dlp 解析失败: {e}{hint}") from e

    minio_video_url = None
    video_object_key = _minio_object_key("uploads", job_id, filename)
    if _minio_enabled():
        try:
            minio_video_url = _minio_upload_file(output_path, video_object_key, content_type="video/mp4")
        except Exception:
            minio_video_url = None

    return {
        "job_id": job_id,
        "filename": filename,
        "video_path": f"{job_id}/{filename}",
        "video_url": minio_video_url or f"http://localhost:8000/uploads/{job_id}/{filename}",
        "title": title,
        "platform": platform,
        "source_url": source_url,
        "object_key": video_object_key if minio_video_url else "",
    }

@app.post("/analyze")
async def analyze_video(
    video: UploadFile = File(...),
    config_json: str = Form(...)
):
    async def event_generator():
        try:
            config = json.loads(config_json)
            
            # 保存上传的文件
            job_id = str(uuid.uuid4())
            job_dir = os.path.join(UPLOAD_DIR, job_id)
            os.makedirs(job_dir, exist_ok=True)
            
            video_path = os.path.join(job_dir, video.filename)
            with open(video_path, "wb") as buffer:
                shutil.copyfileobj(video.file, buffer)

            video_url_public = f"http://localhost:8000/uploads/{job_id}/{video.filename}"
            if _minio_enabled():
                try:
                    yield json.dumps({"status": "progress", "message": "正在上传视频到 MinIO..."}) + "\n"
                    video_object_key = _minio_object_key("uploads", job_id, video.filename)
                    video_url_public = _minio_upload_file(video_path, video_object_key, content_type="video/mp4")
                except Exception:
                    video_url_public = f"http://localhost:8000/uploads/{job_id}/{video.filename}"
            
            yield json.dumps({"status": "progress", "message": "视频上传成功，开始分析..."}) + "\n"

            # 进度回调
            def progress_callback(msg):
                # 这是一个同步回调，但在异步生成器中我们需要处理它
                # 我们将消息放入队列或直接 yield (由于是在同一线程运行 analyzer.run)
                pass

            # 为了在 SSE 中发送消息，我们需要一个队列
            queue = asyncio.Queue()
            
            def sync_callback(msg):
                # 这个函数会被 FastVideoAnalyzer 同步调用
                asyncio.run_coroutine_threadsafe(queue.put(msg), loop)

            loop = asyncio.get_event_loop()
            output_dir = os.path.join("fast_output", job_id)
            
            # 在单独的线程中运行分析，避免阻塞事件循环
            analyzer = FastVideoAnalyzer(video_path, output_dir, config=config, progress_callback=lambda m: queue.put_nowait(m))

            # 启动分析任务
            task = asyncio.create_task(asyncio.to_thread(analyzer.run))

            # 监听队列并 yield 消息
            while not task.done() or not queue.empty():
                try:
                    # 等待消息，带有超时以便检查任务是否完成
                    msg = await asyncio.wait_for(queue.get(), timeout=0.5)
                    yield json.dumps({"status": "progress", "message": msg}) + "\n"
                except asyncio.TimeoutError:
                    continue

            ai_analysis = task.result()
            
            if ai_analysis:
                report_path = os.path.join(output_dir, "final_report.md")
                use_minio_assets = False
                if _minio_enabled():
                    try:
                        yield json.dumps({"status": "progress", "message": "正在上传分析产物到 MinIO..."}) + "\n"
                        _minio_upload_tree(output_dir, _minio_object_key("outputs", job_id))
                        use_minio_assets = True
                    except Exception:
                        use_minio_assets = False

                with open(report_path, "r", encoding="utf-8") as f:
                    report_content = f.read()

                if use_minio_assets:
                    for seg in ai_analysis.get("segments", []):
                        if "image_path" in seg:
                            image_object_key = _minio_object_key("outputs", job_id, seg["image_path"])
                            seg["image_url"] = _minio_presigned_url(image_object_key)
                            report_content = report_content.replace(f"]({seg['image_path']})", f"]({seg['image_url']})")
                    outputs_base_url = "minio"
                else:
                    outputs_base_url = f"http://localhost:8000/outputs/{job_id}/"
                    for seg in ai_analysis.get("segments", []):
                        if "image_path" in seg:
                            seg["image_url"] = f"{outputs_base_url}{seg['image_path']}"
                    report_content = report_content.replace("](images/", f"]({outputs_base_url}images/")
                
                yield json.dumps({
                    "status": "success",
                    "report": report_content,
                    "data": ai_analysis,
                    "video_url": video_url_public,
                    "video_path": f"{job_id}/{video.filename}",
                    "outputs_base_url": outputs_base_url,
                }) + "\n"
            else:
                yield json.dumps({"status": "error", "message": "分析失败，无法生成报告"}) + "\n"
                
        except Exception as e:
            print(f"Error during analysis: {e}")
            yield json.dumps({"status": "error", "message": str(e)}) + "\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/analyze_path")
async def analyze_video_by_path(request: AnalyzePathRequest):
    async def event_generator():
        try:
            rel_path = request.video_path or ""
            rel_url_path = rel_path.replace("\\", "/").lstrip("/")
            abs_path = _safe_join(UPLOAD_DIR, rel_url_path)
            if not os.path.isfile(abs_path):
                raise RuntimeError("视频文件不存在")

            config = request.config.model_dump()
            yield json.dumps({"status": "progress", "message": "视频加载成功，开始分析..."}) + "\n"

            queue = asyncio.Queue()
            job_id = rel_url_path.split("/", 1)[0] if "/" in rel_url_path else os.path.splitext(os.path.basename(rel_url_path))[0]
            output_dir = os.path.join("fast_output", job_id)
            analyzer = FastVideoAnalyzer(abs_path, output_dir, config=config, progress_callback=lambda m: queue.put_nowait(m))
            task = asyncio.create_task(asyncio.to_thread(analyzer.run))

            while not task.done() or not queue.empty():
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=0.5)
                    yield json.dumps({"status": "progress", "message": msg}) + "\n"
                except asyncio.TimeoutError:
                    continue

            ai_analysis = task.result()
            if ai_analysis:
                report_path = os.path.join(output_dir, "final_report.md")
                use_minio_assets = False
                if _minio_enabled():
                    try:
                        yield json.dumps({"status": "progress", "message": "正在上传分析产物到 MinIO..."}) + "\n"
                        _minio_upload_tree(output_dir, _minio_object_key("outputs", job_id))
                        use_minio_assets = True
                    except Exception:
                        use_minio_assets = False

                with open(report_path, "r", encoding="utf-8") as f:
                    report_content = f.read()

                if use_minio_assets:
                    for seg in ai_analysis.get("segments", []):
                        if "image_path" in seg:
                            image_object_key = _minio_object_key("outputs", job_id, seg["image_path"])
                            seg["image_url"] = _minio_presigned_url(image_object_key)
                            report_content = report_content.replace(f"]({seg['image_path']})", f"]({seg['image_url']})")
                    outputs_base_url = "minio"
                else:
                    outputs_base_url = f"http://localhost:8000/outputs/{job_id}/"
                    for seg in ai_analysis.get("segments", []):
                        if "image_path" in seg:
                            seg["image_url"] = f"{outputs_base_url}{seg['image_path']}"
                    report_content = report_content.replace("](images/", f"]({outputs_base_url}images/")

                video_url_public = f"http://localhost:8000/uploads/{rel_url_path}"
                if _minio_enabled():
                    try:
                        yield json.dumps({"status": "progress", "message": "正在上传视频到 MinIO..."}) + "\n"
                        video_object_key = _minio_object_key("uploads", job_id, os.path.basename(rel_url_path))
                        video_url_public = _minio_upload_file(abs_path, video_object_key, content_type="video/mp4")
                    except Exception:
                        video_url_public = f"http://localhost:8000/uploads/{rel_url_path}"

                yield json.dumps(
                    {
                        "status": "success",
                        "report": report_content,
                        "data": ai_analysis,
                        "video_url": video_url_public,
                        "video_path": rel_url_path,
                        "outputs_base_url": outputs_base_url,
                    }
                ) + "\n"
            else:
                yield json.dumps({"status": "error", "message": "分析失败，无法生成报告"}) + "\n"
        except Exception as e:
            print(f"Error during analysis: {e}")
            yield json.dumps({"status": "error", "message": str(e)}) + "\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/import_video_url")
async def import_video_url(request: ImportVideoUrlRequest):
    try:
        result = await asyncio.to_thread(_import_video_from_url, request.url)
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/translate")
async def translate_subtitles(request: TranslateRequest):
    lines = request.lines or []
    if not lines:
        return {"translations": []}

    try:
        translated_texts = await asyncio.to_thread(translate_lines, lines, request.config.device)
        translations = [{"index": i, "text": text} for i, text in enumerate(translated_texts)]
        return {"translations": translations}
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Translation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


OCR_PROMPT = """
**任务要求** 
 请作为专业级OCR处理引擎，对输入的图像执行以下精准操作： 
 
 **核心功能** 
 
 1. **多字体解析** 
    - 准确识别20+中文字体（如宋体、黑体、楷体等）及15+英文字体（如Arial、Times New Roman等）。 
 2. **版式还原技术** 
    - 自动检测文本方向（支持0-360度旋转校正）。 
    - 保留段落间距（精度±1像素），还原原始分栏结构。 
    - 支持复杂版式解析，包括混合布局、倾斜文本及分栏页面。 
 3. **智能纠错系统** 
    - 模糊文本增强处理（当分辨率低于150dpi时自动启用）。 
    - 相似字符差分校验（如0/O、1/l/i等，自动进行上下文校正）。 
    - 搭载智能语言模型，自动纠正常见拼写和语法错误。 
 4. **格式识别与还原** 
    - **代码块**：支持Markdown格式代码块的识别，自动识别代码块的起始和结束标记（如```），并保留代码块内的格式、缩进和注释。 
    - **标题**：识别各级标题（如#、##、###等），并保留其格式。 
    - **列表**：支持有序列表（如1.、a.）和无序列表（如-、*）的识别，保留列表结构。 
    - **引用**：识别引用文本（如>），并保留其格式。 
    - **加粗与斜体**：识别加粗（如**bold**）和斜体（如*italic*）文本，并保留其格式。 
    - **表格**：支持Markdown格式表格的识别，保留表格结构和对齐方式。 
 
 **处理标准** 
 
 - **中英混合文本识别准确率**：≥99.5%（符合GB/T 37094-2018标准）。 
 - **表格识别**：支持合并单元格检测，列宽对齐误差小于2字符。 
 - **特殊内容处理**： 
   - 数学公式保持LaTeX格式。 
   - 程序代码保留缩进与注释，支持Markdown格式代码块的识别。 
   - 手写体标注[Handwritten]标签。 
   - 对扫描件进行深度增强处理，支持多页文档整合。 
 
 **输出规范** 
 
 - **编码格式**：纯文本输出，编码为UTF-8 with BOM。 
 - **禁忌事项**：不添加识别置信度说明，不修改原始内容顺序。 
 - **渲染要求**：不要将整个输出包裹在代码块围栏（```）中；仅当原图内容本身是代码块时才保留围栏。表格请输出标准 Markdown 表格（`|` + `---` 分隔行），不要用 ASCII 画线表格。 
 - **最终要求**：输出仅为OCR后的原始文本，确保无任何附加信息，且完全保留原格式，包括Markdown代码块、标题、列表、引用、加粗与斜体等格式。 
"""

@app.post("/ocr_courseware")
async def ocr_courseware(request: CoursewareOcrRequest):
    items = request.items or []
    if not items:
        return {"results": []}

    def run():
        results = []
        for item in items:
            image_path = None
            try:
                image_path = _local_path_from_url(item.url)
            except Exception:
                image_path = None

            try:
                if image_path and os.path.isfile(image_path):
                    text = analyze_image_with_vl_model(request.config, image_path, prompt=OCR_PROMPT)
                else:
                    parsed = urlparse(item.url)
                    if parsed.scheme in ("http", "https"):
                        image_bytes, content_type = _download_image_bytes(item.url)
                        mime_type = (content_type.split(";", 1)[0].strip() if content_type else "").lower()
                        if not mime_type.startswith("image/"):
                            guessed = mimetypes.guess_type(unquote(parsed.path or ""))[0] or ""
                            mime_type = guessed.lower() if guessed else "image/jpeg"
                        text = analyze_image_with_vl_model_bytes(request.config, image_bytes, mime_type=mime_type, prompt=OCR_PROMPT)
                    else:
                        raise RuntimeError(f"图片不存在: {image_path or item.url}")
            except Exception as e:

                print(f"OCR failed for {item.url}: {e}")
                text = f"[Error: {e}]"
                
            results.append({
                "timestamp": float(item.timestamp),
                "name": item.name,
                "url": item.url,
                "text": text,
            })
        results.sort(key=lambda x: x.get("timestamp", 0))
        return results

    try:
        results = await asyncio.to_thread(run)
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    try:
        data = await websocket.receive_json()
        # 解析数据，兼容前端传来的结构
        if "messages" in data:
            messages = data["messages"]
            transcript = data.get("transcript", "")
            summary = data.get("summary", "")
            config_data = data.get("config", {})
        else:
            # 兼容旧格式（虽然前端已经更新）
            messages = [{"role": "user", "content": "Hello"}] # Dummy
            transcript = ""
            summary = ""
            config_data = {}

        # 构造 ConfigModel
        config = ConfigModel(
            openai_api_key=config_data.get("openai_api_key", ""),
            openai_base_url=config_data.get("openai_base_url", ""),
            llm_model=config_data.get("llm_model", ""),
            asr_mode=config_data.get("asr_mode", "local"),
            model_size=config_data.get("model_size", "medium"),
            device=config_data.get("device", "cuda"),
            compute_type=config_data.get("compute_type", "float16"),
            capture_offset=float(config_data.get("capture_offset", 5.0))
        )

        client = AsyncOpenAI(
            api_key=config.openai_api_key,
            base_url=config.openai_base_url
        )

        system_prompt = (
            "你是一个专业的视频内容助手。你可以根据视频的字幕内容和摘要回答用户的问题。\n"
            f"视频摘要：{summary}\n"
            f"视频字幕片段：{transcript[:5000]}...\n" # 提供部分字幕上下文
            "请以Markdown格式回答。如果需要进行详细解释，请使用 <think>...</think> 包裹思考过程。"
        )

        chat_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            chat_messages.append({"role": msg["role"], "content": msg["content"]})

        # 尝试创建流式响应，增加自动回退机制
        response = None
        current_model = config.llm_model
        # 备选模型列表
        fallbacks = ["deepseek-ai/DeepSeek-V2.5", "Qwen/Qwen2.5-7B-Instruct", "deepseek-ai/DeepSeek-V3"]
        
        async def create_chat_stream(model_name):
            return await client.chat.completions.create(
                model=model_name,
                messages=chat_messages,
                stream=True
            )

        try:
            response = await create_chat_stream(current_model)
        except Exception as e:
            error_str = str(e)
            # 检查是否是模型不存在错误 (Code 20012 or 400)
            if "Model does not exist" in error_str or "400" in error_str:
                print(f"Chat model {current_model} failed, trying fallbacks...")
                success = False
                for fallback in fallbacks:
                    if fallback == current_model: continue
                    try:
                        print(f"Trying fallback chat model: {fallback}")
                        response = await create_chat_stream(fallback)
                        success = True
                        break
                    except Exception as inner_e:
                        print(f"Fallback {fallback} failed: {inner_e}")
                
                if not success:
                    raise e
            else:
                raise e

        async for chunk in response:
            if not chunk.choices: continue
            delta = chunk.choices[0].delta
            
            # Check for reasoning content (DeepSeek R1 style)
            # Note: Standard OpenAI API might not return reasoning_content, check safely
            reasoning = getattr(delta, 'reasoning_content', None)
            if reasoning:
                 await websocket.send_json({"type": "reasoning", "delta": reasoning})
            
            # Check for standard content
            if delta.content:
                await websocket.send_json({"type": "content", "delta": delta.content})

    except Exception as e:
        await websocket.send_json({"type": "error", "content": str(e)})
    finally:
        await websocket.close()

@app.post("/generate_mindmap")
async def generate_mindmap(request: MindMapRequest):
    client = AsyncOpenAI(
        api_key=request.config.openai_api_key,
        base_url=request.config.openai_base_url
    )
    
    system_prompt = """
    你是一个思维导图专家。请根据用户提供的视频字幕内容，生成一个结构化的思维导图数据。
    返回格式必须是符合 G6 TreeGraph 的 JSON 数据结构。
    
    结构示例：
    {
      "id": "root",
      "label": "核心主题",
      "children": [
        {
          "id": "c1",
          "label": "分支1",
          "children": [
            {"id": "c1-1", "label": "子节点1"}
          ]
        }
      ]
    }
    
    要求：
    1. 根节点应该是视频的主题。
    2. 第一层子节点是主要章节或关键话题。
    3. 后续子节点是详细知识点。
    4. 确保 id 唯一。
    5. 只返回 JSON，不要包含 Markdown 格式标记 (如 ```json)。
    """
    
    try:
        # Fallback logic for LLM model
        model_name = request.config.llm_model
        fallback_model = os.getenv("LLM_MODEL", "").strip()
        
        # Try primary model first, if fails with model error, try fallback
        try:
             response = await client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"视频字幕内容如下：\n{request.transcript[:20000]}"}
                ]
             )
        except Exception as e:
            # Check if error is related to model not existing (code 400 or specific message)
            error_str = str(e)
            if "Model does not exist" in error_str or "400" in error_str:
                if fallback_model and fallback_model != model_name:
                    print(f"Primary model {model_name} failed, trying fallback: {fallback_model}")
                    response = await client.chat.completions.create(
                        model=fallback_model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": f"视频字幕内容如下：\n{request.transcript[:20000]}"}
                        ]
                    )
                else:
                    raise e
            else:
                raise e

        content = response.choices[0].message.content
        # 尝试清理可能存在的 markdown 标记
        if content.startswith("```json"):
            content = content.replace("```json", "", 1).replace("```", "", 1).strip()
        elif content.startswith("```"):
            content = content.replace("```", "", 1).strip()
            if content.endswith("```"):
                content = content[:-3].strip()
        
        return json.loads(content)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error generating mindmap: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate_notes")
async def generate_notes(request: NotesRequest):
    print(">>> Generating notes...")
    system_prompt = """你是一个专业的课程笔记整理助手。请根据提供的视频字幕内容，整理出一份结构清晰、重点突出的Markdown格式笔记。
    
要求：
1. 使用一级标题、二级标题等Markdown语法组织内容。
2. 提取关键概念和定义，并用加粗显示。
3. 总结每个章节的核心要点。
4. 如果有列表内容，请使用无序或有序列表。
5. 保持语言简洁流畅，适合复习和查阅。
6. 不要包含“视频”、“字幕”等词汇，直接呈现知识内容。
"""
    
    model_name = request.config.llm_model
    
    # Helper function to call LLM (reuse logic if possible, or just duplicate for now)
    # Since we don't have a shared async LLM wrapper in this scope easily without refactoring,
    # we'll instantiate a client.
    
    client = AsyncOpenAI(
        api_key=request.config.openai_api_key,
        base_url=request.config.openai_base_url
    )
    
    async def call_llm(model):
        return await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"视频字幕内容如下：\n{request.transcript[:25000]}"} # Limit context length
            ]
        )

    try:
        response = await call_llm(model_name)
    except BadRequestError as e:
        # Check for model not found error (SiliconFlow code 20012 or generic message)
        is_model_error = "Model does not exist" in str(e) or (e.body and e.body.get("code") == 20012)
        if is_model_error:
            print(f"Model {model_name} failed, trying fallbacks...")
            # Common fallback models for SiliconFlow
            fallbacks = ["deepseek-ai/DeepSeek-V2.5", "Qwen/Qwen2.5-7B-Instruct", "deepseek-ai/DeepSeek-V3"]
            success = False
            for fallback in fallbacks:
                if fallback == model_name: continue
                try:
                    print(f"Trying fallback model: {fallback}")
                    response = await call_llm(fallback)
                    success = True
                    break
                except Exception as inner_e:
                    print(f"Fallback {fallback} failed: {inner_e}")
            
            if not success:
                raise e
        else:
            raise e
            
    content = response.choices[0].message.content
    return {"notes": content}



class CaptureRequest(BaseModel):
    video_filename: str
    timestamp: float


@app.post("/capture_frame")
async def capture_frame(request: CaptureRequest):
    print(f">>> Capturing frame for {request.video_filename} at {request.timestamp}s...")
    rel_video_path = (request.video_filename or "").replace("\\", "/").lstrip("/")
    video_path = os.path.join(UPLOAD_DIR, rel_video_path)
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video file not found")
    
    job_id = rel_video_path.split("/", 1)[0] if "/" in rel_video_path else os.path.splitext(os.path.basename(rel_video_path))[0]
    output_dir = os.path.join("fast_output", job_id)
    
    # We don't need full config for capture, just path
    analyzer = FastVideoAnalyzer(
        video_path=video_path,
        output_dir=output_dir,
        config={} 
    )
    
    loop = asyncio.get_event_loop()
    try:
        image_path = await loop.run_in_executor(
            None, 
            lambda: analyzer.capture_frame(timestamp=request.timestamp)
        )
    except Exception as e:
        print(f"Frame capture failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
    if not image_path:
        raise HTTPException(status_code=500, detail="Failed to capture frame")

    # Construct URL
    base_url = "http://localhost:8000"
    p_normalized = image_path.replace(os.sep, "/")
    url = f"{base_url}/outputs/{job_id}/{p_normalized}"
    if _minio_enabled():
        try:
            object_key = _minio_object_key("outputs", job_id, p_normalized)
            url = _minio_upload_file(os.path.join(output_dir, image_path), object_key, content_type="image/jpeg")
        except Exception:
            url = f"{base_url}/outputs/{job_id}/{p_normalized}"
        
    return {"url": url, "timestamp": request.timestamp}



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
