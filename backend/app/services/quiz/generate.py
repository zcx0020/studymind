"""quiz/generate.py —— 按学习计划批量出题（与 plan 模块挂钩）
成本策略：该知识点已有"该用户未答过"的题则直接复用，不足才调 LLM 生成
自适应：出题前读取该知识点最近的诊断报告，按其策略调整难度/层次/干扰项（M6）
"""
import json
from typing import List, Optional

from app.services.quiz.mastery import get_theta
from app.services.rag.adaptive_quiz import AdaptiveQuizService


def _rows_as_dicts(cur) -> list:
    """psycopg2 返回元组行，按列名转 dict"""
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def get_today_tasks(pg_conn, plan_id: int, day_override: Optional[int] = None):
    """今日任务：默认 = 计划中最早有 pending 条目的那天（可前端传 day 切换）"""
    with pg_conn.cursor() as cur:
        if day_override is None:
            cur.execute("""SELECT MIN(day_index) FROM plan_items
                           WHERE plan_id=%s AND status='pending'""", (plan_id,))
            day_override = cur.fetchone()[0] or 1
        cur.execute("""SELECT pi.id AS plan_item_id, pi.task_type, pi.est_minutes,
                              kp.id AS kp_id, kp.name, kp.definition,
                              kp.document_id AS doc_id
                       FROM plan_items pi
                       JOIN knowledge_points kp ON kp.id = pi.knowledge_point_id
                       WHERE pi.plan_id=%s AND pi.day_index=%s
                       ORDER BY pi.id""", (plan_id, day_override))
        rows = _rows_as_dicts(cur)
    return day_override, rows


def get_latest_diagnosis(pg_conn, user_id: int, kp_id: int) -> Optional[dict]:
    """该知识点最近一次诊断报告 → 出题策略（难度/Bloom/干扰项个性化，M6）"""
    with pg_conn.cursor() as cur:
        cur.execute("""SELECT root_cause, remedy_path, next_strategy, confused_concepts
                       FROM diagnosis_reports
                       WHERE user_id=%s AND weak_kp_id=%s
                       ORDER BY created_at DESC LIMIT 1""", (user_id, kp_id))
        row = cur.fetchone()
    if not row:
        return None
    return {"root_cause": row[0], "remedy_path": row[1] or [],
            "next_strategy": row[2] or {}, "confused_concepts": row[3] or []}


def ensure_questions(pg_conn, quiz_service: AdaptiveQuizService,
                     user_id: int, kp: dict, theta: float,
                     diagnosis: Optional[dict] = None, count: int = 3) -> List[int]:
    """确保该知识点有 count 道可用题：先复用题库，不足再生成入库。
    补题时并行调 LLM（3 并发）——此前逐题串行 + 每次重试重算题干向量，导致"卡死"观感"""
    from concurrent.futures import ThreadPoolExecutor

    with pg_conn.cursor() as cur:
        cur.execute("""SELECT q.id FROM questions q
                       WHERE q.knowledge_point_id=%s
                         AND NOT EXISTS (SELECT 1 FROM quiz_records r
                                         WHERE r.question_id=q.id AND r.user_id=%s)
                       LIMIT %s""", (kp["kp_id"], user_id, count))
        ids = [r[0] for r in cur.fetchall()]

    need = count - len(ids)
    if need <= 0:
        return ids

    # 现有题干只查一次（注入 Prompt 保证换角度）
    with pg_conn.cursor() as cur:
        cur.execute("SELECT stem FROM questions WHERE knowledge_point_id=%s",
                    (kp["kp_id"],))
        existing_stems = [r[0] for r in cur.fetchall()]

    def _gen(_):
        return quiz_service.generate(user_id, kp, theta, diagnosis=diagnosis,
                                     pg_conn=None, existing_stems=existing_stems)

    with ThreadPoolExecutor(max_workers=min(3, need)) as ex:
        qs = list(ex.map(_gen, range(need)))

    for q in qs:
        with pg_conn.cursor() as cur:
            cur.execute("""INSERT INTO questions
                           (document_id, knowledge_point_id, qtype, stem, options,
                            answer, analysis, difficulty, bloom)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                        (kp["doc_id"], kp["kp_id"], "single_choice", q.stem,
                         json.dumps(q.options, ensure_ascii=False), q.answer,
                         q.analysis, q.difficulty, q.bloom))
            ids.append(cur.fetchone()[0])
        pg_conn.commit()
    return ids


def pregenerate_questions(pg_conn, chroma_client, embedder, doc_id: int,
                          user_id: int = 1, per_kp: int = 2, max_kps: int = 12) -> dict:
    """预生成题目：解析/建库完成后，为前 N 个知识点批量生成题目入库，
    让"开始学习"首屏秒开（不用实时调 LLM）。
    数量受限（max_kps × per_kp）控制成本；未覆盖的知识点仍走实时生成兜底。"""
    from app.services.rag.adaptive_quiz import AdaptiveQuizService, ChromaRetriever

    with pg_conn.cursor() as cur:
        cur.execute("""SELECT id, name, definition FROM knowledge_points
                       WHERE document_id=%s ORDER BY id LIMIT %s""", (doc_id, max_kps))
        cols = [d[0] for d in cur.description]
        kps = [dict(zip(cols, r)) for r in cur.fetchall()]
    if not kps:
        return {"kps": 0, "questions_ready": 0}

    service = AdaptiveQuizService(ChromaRetriever(chroma_client, f"doc_{doc_id}", embedder))
    ready = 0
    for kp in kps:
        kp_data = {"kp_id": kp["id"], "name": kp["name"],
                   "definition": kp["definition"], "doc_id": doc_id}
        theta = get_theta(pg_conn, user_id, kp_data["kp_id"])
        qids = ensure_questions(pg_conn, service, user_id, kp_data, theta, count=per_kp)
        ready += len(qids)
    return {"kps": len(kps), "questions_ready": ready}


def build_today_quiz(pg_conn, plan_id: int, user_id: int, quiz_service,
                     day_override: Optional[int] = None) -> dict:
    """组装今日任务。注意：返回前端的题目剔除 answer/analysis —— 判分只在服务端"""
    day, items = get_today_tasks(pg_conn, plan_id, day_override)
    payload = {"plan_id": plan_id, "day_index": day, "items": []}
    for it in items:
        theta = get_theta(pg_conn, user_id, it["kp_id"])
        diagnosis = get_latest_diagnosis(pg_conn, user_id, it["kp_id"])
        qids = ensure_questions(pg_conn, quiz_service, user_id, it, theta, diagnosis)
        with pg_conn.cursor() as cur:
            cur.execute("""SELECT id, qtype, stem, options, difficulty, bloom
                           FROM questions WHERE id = ANY(%s)""", (qids,))
            questions = _rows_as_dicts(cur)
        payload["items"].append({**it, "theta": round(theta),
                                 "diagnosis": diagnosis, "questions": questions})
    return payload


def fetch_question_full(pg_conn, question_id: int) -> dict:
    """服务端内部取完整题目（含答案），仅判分流程使用，不出接口"""
    with pg_conn.cursor() as cur:
        cur.execute("""SELECT id, knowledge_point_id, qtype, stem, options,
                              answer, analysis, difficulty, bloom
                       FROM questions WHERE id=%s""", (question_id,))
        row = cur.fetchone()
        if row is None:
            return None
        cols = [d[0] for d in cur.description]
    return dict(zip(cols, row))
