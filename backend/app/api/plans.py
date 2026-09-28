"""api/plans.py —— 学习计划：生成（异步）、查询与一键拆分"""
import math

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api import deps
from app.services import taskman
from app.services.plan.generate import generate_plan
from app.services.plan.persist import save_plan

router = APIRouter(prefix="/api/plans", tags=["plans"])


class PlanRequest(BaseModel):
    document_id: int
    user_id: int = 1
    total_days: int = 7
    minutes_per_day: int = 45
    daily_limit: int = 5          # 每日知识点数量上限（1~20，用户自定义）
    goal: str = "掌握该主题全部核心内容"


@router.post("/generate")
def generate(req: PlanRequest):
    """生成学习计划。异步任务：轮询 /api/tasks/{task_id}"""
    t = taskman.run_task("plan_generate", _build_plan, req)
    return {"task_id": t.id}


def _build_plan(t: taskman.TaskState, req: PlanRequest) -> dict:
    t.stage = "拉取图谱 + 拓扑排序 + 任务装箱"
    t.progress = 20
    pg = deps.new_pg()
    try:
        with pg.cursor() as cur:
            cur.execute("SELECT title FROM documents WHERE id=%s", (req.document_id,))
            row = cur.fetchone()
        if row is None:
            raise HTTPException(404, "教材不存在")
        subject, _, topic = row[0].partition(" · ")
        t.stage = "LLM 撰写每日学习文案"
        t.progress = 60
        plan = generate_plan(req.user_id, req.document_id, deps.get_neo4j(), pg,
                             req.total_days, req.minutes_per_day, req.goal,
                             subject, topic, daily_limit=req.daily_limit)
        plan_id = save_plan(pg, req.user_id, plan)
    finally:
        pg.close()
    return {"plan_id": plan_id, "total_days": plan["total_days"],
            "requested_days": plan["requested_days"], "extended": plan["extended"],
            "daily_limit": plan["daily_limit"], "leftovers": plan["leftovers"]}


@router.get("")
def list_plans(user_id: int = 1, pg=Depends(deps.get_pg)):
    """计划列表（前端下拉选择）"""
    with pg.cursor() as cur:
        cur.execute("""SELECT p.id, p.document_id, p.goal, p.total_days, p.status,
                              COALESCE(p.daily_limit, 5) AS daily_limit,
                              p.created_at, d.title
                       FROM study_plans p
                       JOIN documents d ON d.id = p.document_id
                       WHERE p.user_id=%s ORDER BY p.id DESC""", (user_id,))
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    return {"items": rows}


@router.post("/{plan_id}/rebalance")
def rebalance(plan_id: int, pg=Depends(deps.get_pg)):
    """一键拆分：pending 任务按现有顺序重排，每天最多 = 计划自定义的 daily_limit，
    超出顺延到后续天数；总容量不足时自动延长计划天数。保持原 (day, id) 相对顺序 → 拓扑序不破坏"""
    with pg.cursor() as cur:
        cur.execute("""SELECT id, day_index FROM plan_items
                       WHERE plan_id=%s AND status='pending'
                       ORDER BY day_index, id""", (plan_id,))
        rows = cur.fetchall()
        if not rows:
            return {"moved": 0, "note": "没有待调整的任务"}
        cur.execute("""SELECT total_days, COALESCE(daily_limit, 5) FROM study_plans
                       WHERE id=%s""", (plan_id,))
        row = cur.fetchone()
        if row is None:
            raise HTTPException(404, "计划不存在")
        total_days, daily_limit = row

    needed = max(total_days, math.ceil(len(rows) / daily_limit))
    if needed > total_days:
        with pg.cursor() as cur:
            cur.execute("UPDATE study_plans SET total_days=%s WHERE id=%s", (needed, plan_id))
            pg.commit()
        total_days = needed

    moved = 0
    with pg.cursor() as cur:
        for i, (item_id, old_day) in enumerate(rows):
            new_day = i // daily_limit + 1
            if new_day != old_day:
                cur.execute("UPDATE plan_items SET day_index=%s WHERE id=%s", (new_day, item_id))
                moved += 1
        pg.commit()
    return {"moved": moved, "total_days": total_days, "max_per_day": daily_limit}


@router.get("/{plan_id}")
def get_plan(plan_id: int, pg=Depends(deps.get_pg)):
    """计划详情：按天分组（created_by 区分初始任务与动态调整插入的任务）"""
    with pg.cursor() as cur:
        cur.execute("""SELECT pi.day_index, pi.task_type, pi.est_minutes, pi.status,
                              pi.created_by, kp.id AS kp_id, kp.name, kp.kp_type,
                              kp.definition
                       FROM plan_items pi
                       JOIN knowledge_points kp ON kp.id = pi.knowledge_point_id
                       WHERE pi.plan_id=%s ORDER BY pi.day_index, pi.id""", (plan_id,))
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    days = {}
    for r in rows:
        days.setdefault(r["day_index"], []).append(r)
    return {"plan_id": plan_id, "days": days}
