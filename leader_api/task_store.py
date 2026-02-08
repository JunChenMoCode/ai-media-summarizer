import asyncio
import uuid
import time
import logging
import traceback
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel

# Simple in-memory storage
class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Task(BaseModel):
    id: str
    url: str
    type: str = "video"  # video or file
    status: TaskStatus = TaskStatus.PENDING
    progress: int = 0
    logs: List[str] = []
    created_at: float
    result: Optional[Dict] = None
    error: Optional[str] = None

# Global store
tasks: Dict[str, Task] = {}
queue = asyncio.Queue()

def get_all_tasks():
    # Sort by created_at desc
    return sorted(tasks.values(), key=lambda x: x.created_at, reverse=True)

def get_task(task_id: str):
    return tasks.get(task_id)

def add_task(url: str, task_type: str = "video"):
    task_id = str(uuid.uuid4())
    task = Task(
        id=task_id,
        url=url,
        type=task_type,
        created_at=time.time(),
        status=TaskStatus.PENDING
    )
    tasks[task_id] = task
    queue.put_nowait(task_id)
    return task

def cancel_task(task_id: str):
    task = tasks.get(task_id)
    if task:
        if task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
            task.status = TaskStatus.CANCELLED
            task.logs.append("Task cancelled by user.")
        return True
    return False

def delete_task(task_id: str):
    if task_id in tasks:
        del tasks[task_id]
        return True
    return False
