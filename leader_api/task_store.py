import asyncio
import uuid
import time
import logging
import traceback
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel

try:
    from .mysql_store import (
        mysql_enabled, db_add_task, db_get_all_tasks, db_get_task, 
        db_update_task, db_delete_task
    )
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

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
    config: Optional[Dict] = None

    def save(self):
        """Helper to save current state to DB if enabled"""
        if HAS_MYSQL and mysql_enabled():
            db_update_task(
                self.id,
                status=self.status,
                progress=self.progress,
                result=self.result,
                error=self.error,
                logs=self.logs
            )

# Global store
tasks: Dict[str, Task] = {}
queue = asyncio.Queue()

def _load_tasks_from_db():
    if not HAS_MYSQL or not mysql_enabled():
        return
    
    db_tasks = db_get_all_tasks()
    for dt in db_tasks:
        try:
            task = Task(
                id=dt["id"],
                url=dt["url"],
                type=dt["type"],
                status=TaskStatus(dt["status"]),
                progress=dt["progress"],
                created_at=dt["created_at"],
                result=dt["result"],
                error=dt["error"],
                config=dt["config"],
                logs=dt["logs"] or []
            )
            tasks[task.id] = task
            # If task was pending or running when server stopped, we might want to 
            # re-queue it or mark it as failed/cancelled.
            # For now, let's re-queue pending tasks. Running tasks might need special handling (e.g. mark failed)
            if task.status == TaskStatus.PENDING:
                queue.put_nowait(task.id)
            elif task.status == TaskStatus.RUNNING:
                # Mark as failed since process restarted
                task.status = TaskStatus.FAILED
                task.error = "Interrupted by server restart"
                task.save()
        except Exception as e:
            print(f"Error loading task {dt.get('id')}: {e}")

# Initial load
_load_tasks_from_db()

def get_all_tasks():
    # Sort by created_at desc
    return sorted(tasks.values(), key=lambda x: x.created_at, reverse=True)

def get_task(task_id: str):
    return tasks.get(task_id)

def add_task(url: str, task_type: str = "video", config: Optional[Dict] = None, created_at: float = 0.0):
    task_id = str(uuid.uuid4())
    task = Task(
        id=task_id,
        url=url,
        type=task_type,
        created_at=created_at if created_at and created_at > 0 else time.time(),
        status=TaskStatus.PENDING,
        config=config,
    )
    tasks[task_id] = task
    
    if HAS_MYSQL and mysql_enabled():
        db_add_task(task_id, url, task_type, task.created_at, config)
        
    queue.put_nowait(task_id)
    return task

def cancel_task(task_id: str):
    task = tasks.get(task_id)
    if task:
        if task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
            task.status = TaskStatus.CANCELLED
            task.logs.append("Task cancelled by user.")
            task.save()
        return True
    return False

def delete_task(task_id: str):
    if task_id in tasks:
        del tasks[task_id]
        if HAS_MYSQL and mysql_enabled():
            db_delete_task(task_id)
        return True
    return False
