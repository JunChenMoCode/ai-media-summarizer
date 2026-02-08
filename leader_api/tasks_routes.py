from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .task_store import add_task, get_all_tasks, cancel_task, delete_task, Task

router = APIRouter()

class EnqueueRequest(BaseModel):
    url: str

@router.post("/enqueue")
def enqueue_task(req: EnqueueRequest):
    task = add_task(req.url, task_type="video")
    return {"status": "queued", "task_id": task.id}

@router.get("")
def list_tasks():
    return get_all_tasks()

@router.delete("/{task_id}")
def remove_task(task_id: str):
    # Try to cancel first
    cancel_task(task_id)
    # Then delete from list
    if delete_task(task_id):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Task not found")
