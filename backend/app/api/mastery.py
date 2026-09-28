"""api/mastery.py —— 掌握度数据（G6 节点着色 / ECharts 看板数据源）"""
from fastapi import APIRouter, Depends

from app.api import deps
from app.config import settings

router = APIRouter(prefix="/api/mastery", tags=["mastery"])


@router.get("/{doc_id}")
def mastery(doc_id: int, user_id: int = 1, pg=Depends(deps.get_pg)):
    """该教材全部知识点的掌握度"""
    with pg.cursor() as cur:
        cur.execute("""SELECT kp.id, kp.name, kp.kp_type,
                              COALESCE(m.elo_theta, 1500.0) AS theta,
                              COALESCE(m.streak, 0) AS streak,
                              COALESCE(m.correct_count, 0) AS correct_count,
                              COALESCE(m.wrong_count, 0) AS wrong_count
                       FROM knowledge_points kp
                       LEFT JOIN mastery_states m
                         ON m.knowledge_point_id = kp.id AND m.user_id = %s
                       WHERE kp.document_id = %s""", (user_id, doc_id))
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    for r in rows:
        r["theta"] = round(r["theta"], 1)
        r["mastered"] = (r["theta"] >= settings.elo_mastered
                         or r["streak"] >= settings.mastered_streak)
        r["is_weak"] = r["theta"] < 1500        # 前端知识点下拉用（🔴 标记）
    return {"doc_id": doc_id, "items": rows}
