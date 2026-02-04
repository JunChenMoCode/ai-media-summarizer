import os
import tempfile
import uuid
import mimetypes
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

from fastapi import APIRouter, HTTPException, Request as FastAPIRequest

from .core import guess_platform_from_url, normalize_proxy_url, public_base_url, sanitize_stem
from .minio_store import minio_enabled, minio_object_key, minio_upload_file
from .models import ImportVideoUrlRequest

try:
    import yt_dlp
except Exception:
    yt_dlp = None

router = APIRouter()


def _looks_like_direct_media_url(url: str) -> str:
    u = (url or "").strip()
    try:
        parsed = urlparse(u)
    except Exception:
        return ""
    if parsed.scheme not in ("http", "https"):
        return ""

    path = unquote(parsed.path or "").lower()
    video_exts = (".mp4", ".mov", ".mkv", ".webm", ".avi", ".flv", ".m4v")
    audio_exts = (".mp3", ".m4a", ".wav", ".flac", ".aac", ".ogg", ".opus")
    if path.endswith(video_exts):
        return "video"
    if path.endswith(audio_exts):
        return "audio"

    try:
        req = Request(u, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=10) as resp:
            ct = (resp.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
            if ct.startswith("video/"):
                return "video"
            if ct.startswith("audio/"):
                return "audio"
    except Exception:
        pass

    return ""


def _download_direct_media(url: str, job_dir: str, kind: str) -> tuple[str, str, str]:
    os.makedirs(job_dir, exist_ok=True)
    parsed = urlparse(url)
    base = os.path.basename(unquote(parsed.path or "")) or "video.mp4"
    if len(base) > 120:
        base = base[-120:]

    name_no_q = base.split("?", 1)[0].split("#", 1)[0].strip()
    if not name_no_q:
        name_no_q = "media"

    title = os.path.splitext(name_no_q)[0] or "media"
    url_ext = os.path.splitext(name_no_q)[1].strip().lower()
    allow_video_ext = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".flv", ".m4v"}
    allow_audio_ext = {".mp3", ".m4a", ".wav", ".flac", ".aac", ".ogg", ".opus"}

    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    content_type = "video/mp4" if kind == "video" else "audio/mpeg"
    with urlopen(req, timeout=30) as resp:
        ct = (resp.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        if (kind == "video" and ct.startswith("video/")) or (kind == "audio" and ct.startswith("audio/")):
            content_type = ct
        ext_map = {
            "video/webm": ".webm",
            "video/x-matroska": ".mkv",
            "video/quicktime": ".mov",
            "video/x-msvideo": ".avi",
            "video/x-flv": ".flv",
            "video/mp4": ".mp4",
            "audio/mpeg": ".mp3",
            "audio/mp3": ".mp3",
            "audio/wav": ".wav",
            "audio/x-wav": ".wav",
            "audio/flac": ".flac",
            "audio/aac": ".aac",
            "audio/ogg": ".ogg",
            "audio/opus": ".opus",
            "audio/mp4": ".m4a",
            "audio/x-m4a": ".m4a",
        }
        allow_ext = allow_video_ext if kind == "video" else allow_audio_ext
        fallback_ext = ".mp4" if kind == "video" else ".mp3"
        ext = url_ext if url_ext in allow_ext else ext_map.get(content_type, fallback_ext)
        filename = sanitize_stem(title) + ext
        out_path = os.path.join(job_dir, filename)
        with open(out_path, "wb") as f:
            while True:
                chunk = resp.read(8 * 1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)

    return out_path, title, content_type


def _yt_dlp_download(url: str, job_dir: str) -> tuple[str, str]:
    """
    用 yt-dlp 下载视频到 job_dir，并返回 (文件路径, 标题)。

    说明：
    - 这里并不关心“下载进度”，因为该接口主要用于一次性导入；
    - 输出模板固定为 download.<ext>，最终会挑选真实生成的文件。
    """
    if yt_dlp is None:
        raise RuntimeError("缺少 yt-dlp 依赖，请先 pip install yt-dlp")

    os.makedirs(job_dir, exist_ok=True)
    before = set()
    try:
        before = set(os.listdir(job_dir))
    except Exception:
        before = set()

    outtmpl = os.path.join(job_dir, "download.%(ext)s")
    proxy = normalize_proxy_url(os.getenv("YTDLP_PROXY", "") or os.getenv("YT_DLP_PROXY", ""))

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


def import_video_from_url(url: str) -> dict:
    """
    从 URL 导入视频到 MinIO。

    输出结构保持与旧版一致：
    - job_id / filename / video_path(object_key) / video_url(presigned) / title / platform / source_url / object_key
    """
    job_id = str(uuid.uuid4())
    source_url = url
    platform = guess_platform_from_url(url)

    if not minio_enabled():
        raise RuntimeError("MinIO 未启用，无法导入视频")

    with tempfile.TemporaryDirectory(prefix="leader-yt-") as job_dir:
        try:
            content_type = "video/mp4"
            media_type = "video"
            direct_kind = _looks_like_direct_media_url(url)
            if direct_kind:
                media_type = direct_kind
                output_path, title, content_type = _download_direct_media(url, job_dir, direct_kind)
                filename = os.path.basename(output_path)
            else:
                downloaded_path, yt_title = _yt_dlp_download(url, job_dir)
                title = yt_title
                ext = os.path.splitext(downloaded_path)[1].strip().lower()
                if ext:
                    audio_exts = {".mp3", ".m4a", ".wav", ".flac", ".aac", ".ogg", ".opus"}
                    video_exts = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".flv", ".m4v"}
                    if ext in audio_exts:
                        media_type = "audio"
                    elif ext in video_exts:
                        media_type = "video"
                filename = sanitize_stem(title) + (ext or ".mp4")
                output_path = os.path.join(job_dir, filename)
                if os.path.abspath(downloaded_path) != os.path.abspath(output_path):
                    os.replace(downloaded_path, output_path)

                guessed = mimetypes.guess_type(output_path)[0] or ""
                if guessed:
                    content_type = guessed
        except Exception as e:
            proxy = normalize_proxy_url(os.getenv("YTDLP_PROXY", "") or os.getenv("YT_DLP_PROXY", ""))
            hint = ""
            if platform == "youtube" and not proxy:
                hint = "（YouTube 可能需要代理，可在 .env 配置 YTDLP_PROXY=http://127.0.0.1:7897）"
            raise RuntimeError(f"URL 导入失败: {e}{hint}") from e

        video_object_key = minio_object_key("uploads", job_id, filename)
        minio_video_url = minio_upload_file(output_path, video_object_key, content_type=content_type)
        return {
            "job_id": job_id,
            "filename": filename,
            "video_path": video_object_key,
            "video_url": minio_video_url,
            "title": title,
            "platform": platform,
            "source_url": source_url,
            "object_key": video_object_key,
            "media_type": media_type,
        }



@router.post("/import_video_url")
async def import_video_url(req: FastAPIRequest, request: ImportVideoUrlRequest):
    """
    URL 导入视频的 HTTP 包装接口。
    """
    try:
        _ = public_base_url(str(req.base_url))  # 保持与旧逻辑一致：此处主要触发 base_url 解析
        import asyncio

        result = await asyncio.to_thread(import_video_from_url, request.url)
        return result
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
