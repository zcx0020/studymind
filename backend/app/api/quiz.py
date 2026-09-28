"""api/quiz.py —— 答题闭环（异步出题 + 亚秒判分 + 异步总结）

接口契约（前端绝不同步等待 LLM）:
  POST /api/quiz/task          出题任务 → 立即返回 task_id（后台线程生成并入库）
  GET  /api/task_status/{id}   任务轮询（出题/批改/诊断/总结通用，见 api/tasks.py）
  POST /api/submit_answer      提交答案：客观题判分+Elo 亚秒返回；
                               主观题转后台 AI 批改（返回 grading_task_id 轮询）；
                               最后一题(is_last=true)触发异步"生成总结"任务，
                               返回 summary_task_id，绝不阻塞当前请求
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api import deps
from app.services import taskman
from app.services.diagnostic.engine import on_mastered, on_wrong_answer
from app.services.quiz.generate import (
    build_today_quiz, ensure_questions, fetch_question_full,
)
from app.services.quiz.grading import grade_objective, grade_subjective
from app.services.quiz.mastery import get_theta, record_and_update
from app.services.quiz.summary import build_summary

logger = logging.getLogger("studymind.quiz")

router = APIRouter(prefix="/api/quiz", tags=["quiz"])
submit_router = APIRouter(prefix="/api", tags=["quiz"])   # 承载 /api/submit_answer


class QuizTaskRequest(BaseModel):
    """异步出题任务参数（mode: today / by_kp / exam）"""
    mode: str = "today"
    plan_id: int | None = None
    day: int | None = None
    kp_id: int | None = None
    doc_id: int | None = None
    count: int | None = None
    user_id: int = 1


class AnswerRequest(BaseModel):
    """提交答案。is_last=True 时触发异步总结任务；
    question_ids = 本次会话全部题目 ID（供总结聚合）；duration_sec = 本题作答耗时"""
    question_id: int
    user_answer: str
    user_id: int = 1
    is_last: bool = False
    question_ids: list[int] = Field(default_factory=list)
    duration_sec: int | None = None


# ══════════════ 内部逻辑（异步任务与接口共用） ══════════════

def _by_kp_payload(pg, kp_id: int, count: int, user_id: int) -> dict:
    if not (1 <= count <= 20):
        raise ValueError("题量需在 1~20 之间")
    with pg.cursor() as cur:
        cur.execute("""SELECT id, name, definition, document_id
                       FROM knowledge_points WHERE id=%s""", (kp_id,))
        row = cur.fetchone()
    if row is None:
        raise ValueError("知识点不存在")
    kp_data = {"kp_id": row[0], "name": row[1], "definition": row[2], "doc_id": row[3]}
    service = deps.get_quiz_service(row[3])
    theta = get_theta(pg, user_id, kp_id)
    qids = ensure_questions(pg, service, user_id, kp_data, theta, count=count)
    with pg.cursor() as cur:
        cur.execute("""SELECT id, qtype, stem, options, difficulty, bloom
                       FROM questions WHERE id = ANY(%s)""", (qids,))
        qcols = [d[0] for d in cur.description]
        qs = [dict(zip(qcols, r)) for r in cur.fetchall()]
    return {"items": [{**kp_data, "theta": round(theta), "questions": qs}]}


def _exam_payload(pg, doc_id: int, count: int, user_id: int) -> dict:
    if not (1 <= count <= 50):
        raise ValueError("题量需在 1~50 之间")
    with pg.cursor() as cur:
        cur.execute("SELECT title FROM documents WHERE id=%s", (doc_id,))
        row = cur.fetchone()
    if row is None:
        raise ValueError("教材不存在")
    title = row[0]

    service = deps.get_quiz_service(doc_id)
    with pg.cursor() as cur:
        cur.execute("""SELECT id, name, definition FROM knowledge_points
                       WHERE document_id=%s ORDER BY RANDOM()""", (doc_id,))
        cols = [d[0] for d in cur.description]
        kps = [dict(zip(cols, r)) for r in cur.fetchall()]

    items, total = [], 0
    for kp in kps:
        if total >= count:
            break
        kp_data = {"kp_id": kp["id"], "name": kp["name"],
                   "definition": kp["definition"], "doc_id": doc_id}
        theta = get_theta(pg, user_id, kp["id"])
        take = min(2, count - total)
        qids = ensure_questions(pg, service, user_id, kp_data, theta, count=take)
        with pg.cursor() as cur:
            cur.execute("""SELECT id, qtype, stem, options, difficulty, bloom
                           FROM questions WHERE id = ANY(%s)""", (qids,))
            qcols = [d[0] for d in cur.description]
            qs = [dict(zip(qcols, r)) for r in cur.fetchall()]
        items.append({**kp_data, "theta": round(theta), "questions": qs})
        total += len(qs)
    return {"doc_id": doc_id, "title": title, "items": items, "total": total}


# ══════════════ ① 异步出题任务（核心：前端不阻塞） ══════════════

@router.post("/task")
def start_quiz_task(req: QuizTaskRequest):
    """出题走后台线程：LLM 生成 + 入库在任务里完成，接口立即返回 task_id。
    题库已有可复用题时任务秒完；新题约 15~20 秒/道。前端轮询 /api/task_status/{id}"""
    logger.info("quiz/task 启动: mode=%s plan=%s kp=%s doc=%s count=%s",
                req.mode, req.plan_id, req.kp_id, req.doc_id, req.count)

    def _build(t: taskman.TaskState, p: dict) -> dict:
        pg = deps.new_pg()
        try:
            mode, user_id = p["mode"], p["user_id"]
            if mode == "today":
                if not p.get("plan_id"):
                    raise ValueError("缺少 plan_id")
                with pg.cursor() as cur:
                    cur.execute("SELECT document_id FROM study_plans WHERE id=%s",
                                (p["plan_id"],))
                    row = cur.fetchone()
                if row is None:
                    raise ValueError("计划不存在")
                t.stage = "AI 正在出题（已预生成的题库秒开，新题约 15~20 秒/道）"
                t.progress = 10
                service = deps.get_quiz_service(row[0])
                payload = build_today_quiz(pg, p["plan_id"], user_id, service, p.get("day"))
                return {"mode": "today", "payload": payload}
            if mode == "by_kp":
                if not p.get("kp_id"):
                    raise ValueError("缺少 kp_id")
                t.stage = "AI 正在出专项题（请稍候）"
                t.progress = 10
                payload = _by_kp_payload(pg, p["kp_id"], p.get("count") or 5, user_id)
                return {"mode": "by_kp", "payload": payload}
            if mode == "exam":
                if not p.get("doc_id"):
                    raise ValueError("缺少 doc_id")
                t.stage = "AI 正在组卷（约 1~2 分钟，请稍候）"
                t.progress = 10
                payload = _exam_payload(pg, p["doc_id"], p.get("count") or 20, user_id)
                return {"mode": "exam", "payload": payload}
            raise ValueError(f"未知出题模式: {mode}")
        finally:
            pg.close()

    t = taskman.run_task("quiz_generate", _build, req.model_dump())
    return {"task_id": t.id}


# ══════════════ ② 提交答案（<1s 契约） ══════════════

def _spawn_diagnosis_task(user_id: int, kp_id: int) -> str:
    """答错 → GraphRAG 诊断 + 计划重排（后台线程，10~30 秒，不阻塞交卷）"""
    def _diag(t, p):
        pg = deps.new_pg()
        try:
            t.stage = "AI 正在分析错因并调整学习计划…"
            return on_wrong_answer(pg, deps.get_neo4j(), p["user_id"], p["kp_id"])
        finally:
            pg.close()
    return taskman.run_task("diagnosis", _diag, {"user_id": user_id, "kp_id": kp_id}).id


def _spawn_grading_task(req: AnswerRequest, q: dict) -> str:
    """主观题 AI 批改（后台线程）：LLM 判分 → Elo 落库 → 返回完整判分结果。
    接口先行返回 grading_task_id，前端轮询拿到对错与评语"""
    def _grade(t, p):
        pg = deps.new_pg()
        try:
            t.stage = "AI 正在按评分细则批改…"
            q2 = fetch_question_full(pg, p["question_id"])
            grading = grade_subjective(q2, p["user_answer"])
            state = record_and_update(pg, p["user_id"], q2, p["user_answer"],
                                      grading.is_correct, grading, p["duration_sec"])
            out = {"is_correct": grading.is_correct, "feedback": grading.feedback,
                   "correct_answer": q2["answer"], "analysis": q2["analysis"],
                   "mastery": state}
            if not grading.is_correct:
                out["diagnosis_task_id"] = _spawn_diagnosis_task(
                    p["user_id"], q2["knowledge_point_id"])
            elif state["mastered"]:
                on_mastered(pg, p["user_id"], q2["knowledge_point_id"])
            return out
        finally:
            pg.close()
    return taskman.run_task("grading", _grade, req.model_dump()).id


def _spawn_summary_task(user_id: int, question_ids: list) -> str:
    """最后一题提交后：异步生成会话总结（纯 DB 聚合、无 LLM，1~2 秒完成）"""
    def _summary(t, p):
        pg = deps.new_pg()
        try:
            t.stage = "正在汇总本次练习…"
            return build_summary(pg, p["user_id"], p["question_ids"])
        finally:
            pg.close()
    return taskman.run_task("quiz_summary", _summary,
                            {"user_id": user_id, "question_ids": question_ids}).id


def _grade_objective_sync(pg, req: AnswerRequest, q: dict) -> dict:
    """客观题同步判分 + Elo 落库：纯 DB 操作，亚秒完成"""
    is_correct = grade_objective(q["qtype"], q["answer"], req.user_answer)
    state = record_and_update(pg, req.user_id, q, req.user_answer,
                              is_correct, None, req.duration_sec)
    logger.info("submit_answer 判分完成: qid=%s correct=%s θ=%s",
                req.question_id, is_correct, state["theta"])
    return {"status": "graded", "is_correct": is_correct,
            "correct_answer": q["answer"], "analysis": q["analysis"],
            "feedback": "回答正确" if is_correct else "回答错误",
            "mastery": state}


def _submit(req: AnswerRequest, pg) -> dict:
    try:
        q = fetch_question_full(pg, req.question_id)
        if q is None:
            raise HTTPException(404, "题目不存在")

        # ① 判分：客观题同步（<1s）；主观题转后台 AI 批改（接口立即返回）
        if q["qtype"] == "short_answer":
            resp = {"status": "grading",
                    "grading_task_id": _spawn_grading_task(req, q),
                    "analysis": q["analysis"]}
        else:
            resp = _grade_objective_sync(pg, req, q)

        # ② 答错 → 异步诊断（LLM + Neo4j + 计划重排，绝不阻塞本次请求）
        if resp.get("is_correct") is False:
            resp["diagnosis_task_id"] = _spawn_diagnosis_task(
                req.user_id, q["knowledge_point_id"])
        elif resp.get("is_correct") is True and resp["mastery"]["mastered"]:
            on_mastered(pg, req.user_id, q["knowledge_point_id"])

        # ③ 最后一题 → 异步生成会话总结，前端拿 summary_task_id 轮询
        if req.is_last and req.question_ids:
            resp["summary_task_id"] = _spawn_summary_task(req.user_id, req.question_ids)
        return resp
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("submit_answer 失败 qid=%s: %s", req.question_id, e)
        raise HTTPException(500, f"提交失败: {e}") from e


@submit_router.post("/submit_answer")
def submit_answer(req: AnswerRequest, pg=Depends(deps.get_pg)):
    """提交答案（新接口）：客观题 <1 秒返回判分+Elo；
    最后一题额外返回 summary_task_id（异步生成总结）"""
    logger.info("submit_answer: qid=%s user=%s is_last=%s",
                req.question_id, req.user_id, req.is_last)
    return _submit(req, pg)


@router.post("/answer")
def answer_alias(req: AnswerRequest, pg=Depends(deps.get_pg)):
    """旧路径别名（兼容 scripts/04_test_api.py），行为与 /api/submit_answer 一致"""
    return _submit(req, pg)
