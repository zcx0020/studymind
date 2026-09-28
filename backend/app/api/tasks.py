"""api/tasks.py —— 异步任务状态查询（前端轮询进度）
提供两个等价路径:
  GET /api/tasks/{task_id}        旧路径（知识库/计划页沿用）
  GET /api/task_status/{task_id}  答题模块统一轮询入口
"""
from fastapi import APIRouter, HTTPException

from app.services import taskman

router = APIRouter(prefix="/api/tasks", tags=["tasks"])
status_router = APIRouter(prefix="/api", tags=["tasks"])


def _status(task_id: str) -> dict:
    t = taskman.get_task(task_id)
    if t is None:
        raise HTTPException(404, "任务不存在")
    return {"id": t.id, "kind": t.kind, "status": t.status,
            "stage": t.stage, "progress": t.progress,
            "result": t.result, "error": t.error}


@router.get("/{task_id}")
def status(task_id: str):
    return _status(task_id)


@status_router.get("/task_status/{task_id}")
def task_status(task_id: str):
    return _status(task_id)
