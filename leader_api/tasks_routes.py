from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any
import json
from .task_store import add_task, get_task, get_all_tasks, cancel_task, delete_task, Task
from .mysql_store import save_app_config, mysql_enabled, db_get_task

router = APIRouter()

class EnqueueRequest(BaseModel):
    url: str
    type: str = "video"  # video or file
    config: Optional[Dict[str, Any]] = None

@router.post("/enqueue")
async def enqueue_task(request: Request):
    try:
        body_bytes = await request.body()
        body_str = body_bytes.decode("utf-8")
        print(f">>> [DEBUG] Raw Request Body: {body_str}")
        
        data = json.loads(body_str)
        # 手动解析，避免 Pydantic 潜在的过滤或转换问题
        req_url = data.get("url")
        req_type = data.get("type", "video")
        req_config = data.get("config")
        
        print(f">>> [DEBUG] Parsed config from JSON: {req_config}")
        
        task = add_task(req_url, task_type=req_type, config=req_config)
        return {"status": "queued", "task_id": task.id}
    except Exception as e:
        print(f">>> [ERROR] Enqueue failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/config")
async def save_latest_config(request: Request):
    try:
        body_bytes = await request.body()
        body_str = body_bytes.decode("utf-8")
        data = json.loads(body_str) if body_str else {}
        raw_cfg = data.get("config", data)
        if isinstance(raw_cfg, str):
            try:
                raw_cfg = json.loads(raw_cfg)
            except Exception:
                raw_cfg = {}
        if not isinstance(raw_cfg, dict):
            raw_cfg = {}
        save_app_config(raw_cfg)
        return {"status": "ok"}
    except Exception as e:
        print(f">>> [ERROR] Save config failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/config")
def get_latest_config():
    try:
        from .mysql_store import load_app_config
        return load_app_config()
    except Exception as e:
        print(f">>> [ERROR] Load config failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("")
def list_tasks(page: int = 1, size: int = 10):
    try:
        from .mysql_store import db_get_all_tasks, db_count_tasks, mysql_enabled
        if mysql_enabled():
            offset = (page - 1) * size
            tasks_data = db_get_all_tasks(limit=size, offset=offset)
            total = db_count_tasks()
            return {
                "total": total,
                "page": page,
                "size": size,
                "items": tasks_data
            }
        else:
            # Fallback to in-memory store
            items = get_all_tasks()
            total = len(items)
            start = (page - 1) * size
            end = start + size
            paged_items = items[start:end]
            res = []
            for t in paged_items:
                try:
                    res.append(t.model_dump(exclude={"config"}))
                except Exception:
                    res.append(t.dict(exclude={"config"}))
            return {
                "total": total,
                "page": page,
                "size": size,
                "items": res
            }
    except Exception as e:
        print(f">>> [ERROR] List tasks failed: {e}")
        # Fallback to old behavior if something breaks
        items = get_all_tasks()
        res = []
        for t in items:
            try:
                res.append(t.model_dump(exclude={"config"}))
            except Exception:
                res.append(t.dict(exclude={"config"}))
        return res

@router.delete("/{task_id}")
def remove_task(task_id: str):
    # Try to cancel first
    cancel_task(task_id)
    # Then delete from list
    if delete_task(task_id):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Task not found")

@router.post("/{task_id}/retry")
def retry_task(task_id: str):
    try:
        task = get_task(task_id)
        if not task and mysql_enabled():
            task_data = db_get_task(task_id)
            if task_data:
                task = Task(**task_data)

        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        if str(task.status) != "failed":
            raise HTTPException(status_code=400, detail="Only failed tasks can be retried")

        new_task = add_task(
            url=task.url,
            task_type=task.type,
            config=task.config,
            created_at=task.created_at,
        )
        return {"status": "queued", "task_id": new_task.id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
