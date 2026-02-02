import uuid

from fastapi import APIRouter, HTTPException, Request as FastAPIRequest

from .minio_store import (
    minio_enabled,
    minio_object_key,
    minio_presigned_put_url,
    minio_presigned_url,
)
from .models import PresignUploadRequest

router = APIRouter()


def _sanitize_filename(name: str) -> str:
    """
    这个接口的 filename 会直接进入 object_key。

    这里做一次轻量清洗：
    - 去掉路径分隔符（避免构造出意外目录结构）
    - 去掉首尾空格
    - 兜底默认值
    """
    n = (name or "").strip().replace("\\", "/")
    n = n.split("/")[-1].strip()
    return n or "video.mp4"


@router.post("/minio/presign_upload")
async def minio_presign_upload(req: FastAPIRequest, request: PresignUploadRequest):
    """
    给前端生成一个“直传 MinIO”用的 presigned PUT URL。

    前端流程：
    1) 请求该接口拿到 upload_url 与 object_key
    2) 直接 PUT 文件到 upload_url（不经过后端转发）
    3) 后续分析/截图等接口把 object_key 当作 video_path 传回后端
    """
    if not minio_enabled():
        raise HTTPException(status_code=400, detail="MinIO 未启用")

    filename = _sanitize_filename(request.filename or "")
    job_id = str(uuid.uuid4())
    object_key = minio_object_key("uploads", job_id, filename)
    upload_url = minio_presigned_put_url(object_key, hours=1)

    return {
        "job_id": job_id,
        "filename": filename,
        "object_key": object_key,
        "upload_url": upload_url,
        "video_url": minio_presigned_url(object_key),
    }

