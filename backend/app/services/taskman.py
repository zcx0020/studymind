"""app/services/taskman.py —— 轻量任务管理器（课程项目版）
内存进度注册表 + 后台线程执行；前端轮询 GET /api/tasks/{id} 拿进度
生产可替换为 Celery+Redis：任务函数签名不变，只需换执行器
"""
import threading
import uuid
from typing import Callable, Optional


class TaskState:
    def __init__(self, kind: str):
        self.id = uuid.uuid4().hex[:12]
        self.kind = kind
        self.status = "pending"      # pending / running / done / failed
        self.stage = ""              # 当前阶段描述（前端展示）
        self.progress = 0            # 0-100
        self.result: Optional[dict] = None
        self.error: Optional[str] = None


_TASKS: dict[str, TaskState] = {}


def create_task(kind: str) -> TaskState:
    t = TaskState(kind)
    _TASKS[t.id] = t
    return t


def get_task(task_id: str) -> Optional[TaskState]:
    return _TASKS.get(task_id)


def run_task(kind: str, fn: Callable[[TaskState, object], dict], payload) -> TaskState:
    """启动后台任务。fn(task, payload) -> result dict，可随时更新 task.stage/progress"""
    t = create_task(kind)
    threading.Thread(target=_exec, args=(t, fn, payload), daemon=True).start()
    return t


def _exec(t: TaskState, fn, payload):
    t.status = "running"
    try:
        t.result = fn(t, payload)
        t.status = "done"
        t.progress = 100
    except Exception as e:            # noqa: BLE001 —— 任务异常要回传给前端
        t.status = "failed"
        t.error = f"{type(e).__name__}: {e}"
