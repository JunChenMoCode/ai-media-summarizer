import os
import re
from urllib.parse import urlparse

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None


def bootstrap_env() -> None:
    """
    负责“启动前环境准备”的集中入口。

    这段逻辑之所以要单独抽出来：
    - main.py 被 uvicorn import 时会立即执行顶层代码；
    - 需要尽早加载 .env，并规范代理变量，避免后续库（如 yt-dlp / requests 等）行为不一致。
    """
    if load_dotenv is not None:
        try:
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


def env_bool(name: str, default: bool = False) -> bool:
    """
    读取形如 1/true/yes/on 的布尔环境变量。
    """
    v = (os.getenv(name, "") or "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "y", "on")


def normalize_proxy_url(proxy: str) -> str:
    """
    将代理字符串规范成带 scheme 的 URL。
    - 输入: 127.0.0.1:7897
    - 输出: http://127.0.0.1:7897
    """
    p = (proxy or "").strip()
    if not p:
        return ""
    if "://" in p:
        return p
    return "http://" + p


def public_base_url(req_base_url: str | None = None) -> str:
    """
    生成对外可访问的 base_url。

    说明：
    - FastAPI 的 request.base_url 是最可靠的来源；
    - 如果没有 request（例如后台线程里）就退回 PUBLIC_BASE_URL；
    - 都没有时使用 localhost + 端口。
    """
    if req_base_url:
        return str(req_base_url).rstrip("/")

    v = (os.getenv("PUBLIC_BASE_URL", "") or "").strip().rstrip("/")
    if v:
        return v

    port_raw = (os.getenv("PORT", "") or "").strip()
    try:
        port = int(port_raw) if port_raw else 18000
    except Exception:
        port = 18000
    return f"http://localhost:{port}"


def sanitize_filename(name: str) -> str:
    """
    生成一个“适合当作 mp4 文件名”的安全字符串：
    - 仅保留中英文、数字、下划线、短横线、点和空格，其余替换成下划线；
    - 过长截断；
    - 确保以 .mp4 结尾（便于后续推断 content-type）。
    """
    base = re.sub(r"[^\w\u4e00-\u9fff\-\.\s]+", "_", (name or "").strip())
    base = re.sub(r"\s+", " ", base).strip()
    if not base:
        base = "video"
    if len(base) > 80:
        base = base[:80].strip()
    if not base.lower().endswith(".mp4"):
        base += ".mp4"
    return base


def guess_platform_from_url(url: str) -> str:
    """
    根据 URL host 粗略推断平台，用于错误提示（例如 YouTube 可能需要代理）。
    """
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

