import io
import mimetypes
import os
from datetime import timedelta

try:
    from minio import Minio
except Exception:
    Minio = None

_MINIO_CLIENT = None


def minio_enabled() -> bool:
    """
    通过 MINIO_ENDPOINT 是否存在来判断是否启用 MinIO。
    """
    return bool(os.getenv("MINIO_ENDPOINT", "").strip())


def _minio_bucket() -> str:
    return os.getenv("MINIO_BUCKET", "leader").strip() or "leader"


def _minio_secure() -> bool:
    v = (os.getenv("MINIO_SECURE", "") or "").strip().lower()
    return v in ("1", "true", "yes", "y")


def _minio_public_base_url() -> str:
    """
    MinIO 对外访问的 base URL。

    - 如果配置了 MINIO_PUBLIC_BASE_URL，则优先使用；
    - 否则根据 MINIO_ENDPOINT 与 MINIO_SECURE 拼出 http/https。
    """
    v = (os.getenv("MINIO_PUBLIC_BASE_URL", "") or "").strip().rstrip("/")
    if v:
        return v
    endpoint = (os.getenv("MINIO_ENDPOINT", "") or "").strip()
    scheme = "https" if _minio_secure() else "http"
    return f"{scheme}://{endpoint}".rstrip("/")


def minio_get_client():
    """
    获取全局复用的 MinIO client。

    说明：
    - 连接对象可安全复用，避免每次请求重复初始化。
    """
    global _MINIO_CLIENT
    if _MINIO_CLIENT is not None:
        return _MINIO_CLIENT
    if not minio_enabled():
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


def minio_ensure_bucket() -> None:
    client = minio_get_client()
    bucket = _minio_bucket()
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)


def guess_content_type(path: str) -> str:
    t, _ = mimetypes.guess_type(path)
    return t or "application/octet-stream"


def minio_object_key(*parts: str) -> str:
    """
    统一拼接对象 key：
    - 去掉多余的 /；
    - Windows 路径分隔符统一替换成 /，避免跨平台问题。
    """
    return "/".join([str(p).strip("/").replace("\\", "/") for p in parts if p is not None and str(p) != ""])


def minio_public_url(object_key: str) -> str:
    base = _minio_public_base_url()
    bucket = _minio_bucket()
    return f"{base}/{bucket}/{object_key.lstrip('/')}"


def minio_presigned_url(object_key: str, days: int = 7) -> str:
    minio_ensure_bucket()
    client = minio_get_client()
    bucket = _minio_bucket()
    return client.presigned_get_object(bucket, object_key, expires=timedelta(days=days))


def minio_presigned_put_url(object_key: str, hours: int = 1) -> str:
    minio_ensure_bucket()
    client = minio_get_client()
    bucket = _minio_bucket()
    return client.presigned_put_object(bucket, object_key, expires=timedelta(hours=hours))


def minio_upload_file(local_path: str, object_key: str, content_type: str | None = None) -> str:
    """
    上传本地文件到 MinIO，并返回可访问的预签名 GET URL。
    """
    minio_ensure_bucket()
    client = minio_get_client()
    bucket = _minio_bucket()
    ct = content_type or guess_content_type(local_path)
    client.fput_object(bucket, object_key, local_path, content_type=ct)
    return minio_presigned_url(object_key)


def minio_upload_stream(stream, object_key: str, length: int | None, content_type: str | None = None) -> str:
    minio_ensure_bucket()
    client = minio_get_client()
    bucket = _minio_bucket()
    ct = (content_type or "").strip() or "application/octet-stream"
    size = int(length) if isinstance(length, int) else -1
    if size < 0:
        client.put_object(bucket, object_key, stream, length=-1, part_size=10 * 1024 * 1024, content_type=ct)
    else:
        client.put_object(bucket, object_key, stream, length=size, content_type=ct)
    return minio_presigned_url(object_key)


def minio_upload_bytes(data: bytes, object_key: str, content_type: str | None = None) -> str:
    return minio_upload_stream(io.BytesIO(data), object_key, len(data), content_type=content_type)


def minio_object_exists(object_key: str) -> bool:
    if not minio_enabled():
        return False
    minio_ensure_bucket()
    client = minio_get_client()
    bucket = _minio_bucket()
    try:
        client.stat_object(bucket, object_key)
        return True
    except Exception:
        return False


def minio_object_etag_md5(object_key: str) -> str:
    if not minio_enabled():
        return ""
    minio_ensure_bucket()
    client = minio_get_client()
    bucket = _minio_bucket()
    try:
        stat = client.stat_object(bucket, object_key)
        etag = (getattr(stat, "etag", "") or "").strip().strip('"').lower()
        if len(etag) == 32 and all(c in "0123456789abcdef" for c in etag):
            return etag
        return ""
    except Exception:
        return ""


def minio_download_to_file(object_key: str, local_path: str) -> None:
    """
    将对象下载到本地临时文件。
    注意：这是“临时下载”，不是长期落盘缓存。
    """
    minio_ensure_bucket()
    client = minio_get_client()
    bucket = _minio_bucket()
    client.fget_object(bucket, object_key, local_path)


def normalize_video_object_key(video_ref: str) -> str:
    """
    将前端传来的 video_path 规范成 MinIO object_key。

    兼容多种输入：
    - uploads/<job_id>/<filename>（已经是完整 key）
    - outputs/<job_id>/<filename>（任务产物 key）
    - <job_id>/<filename>（自动补 uploads/ 前缀）
    """
    ref = (video_ref or "").replace("\\", "/").lstrip("/")
    if not ref:
        return ""
    if ref.startswith("uploads/") or ref.startswith("outputs/"):
        return ref
    return minio_object_key("uploads", ref)


def minio_remove_object(object_key: str) -> None:
    if not minio_enabled():
        return
    minio_ensure_bucket()
    client = minio_get_client()
    bucket = _minio_bucket()
    try:
        client.remove_object(bucket, object_key)
    except Exception:
        pass


def minio_remove_folder(prefix: str) -> None:
    if not minio_enabled():
        return
    minio_ensure_bucket()
    client = minio_get_client()
    bucket = _minio_bucket()
    
    # List all objects with prefix
    objects = client.list_objects(bucket, prefix=prefix, recursive=True)
    for obj in objects:
        try:
            client.remove_object(bucket, obj.object_name)
        except Exception:
            pass

def extract_job_id_from_object_key(object_key: str) -> str:
    k = (object_key or "").replace("\\", "/").lstrip("/")
    if k.startswith("uploads/"):
        rest = k[len("uploads/"):]
        if "/" in rest:
            return rest.split("/", 1)[0]
    return ""


def minio_upload_tree(local_dir: str, object_prefix: str) -> None:
    """
    递归上传整个目录。

    使用场景：
    - FastVideoAnalyzer 产出的图片/markdown/report 都在 output_dir 下；
    - 上传到 outputs/<job_id>/... 便于前端用预签名 URL 访问。
    """
    prefix = minio_object_key(object_prefix)
    for root, _, files in os.walk(local_dir):
        for fn in files:
            local_path = os.path.join(root, fn)
            rel = os.path.relpath(local_path, local_dir).replace(os.sep, "/")
            object_key = minio_object_key(prefix, rel)
            minio_upload_file(local_path, object_key)
