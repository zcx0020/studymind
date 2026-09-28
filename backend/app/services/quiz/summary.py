"""quiz/summary.py —— 练习会话总结（纯 DB 聚合，亚秒完成，供异步任务消费）

数据来源：quiz_records（判分落库时已写入 elo_delta / theta_before 快照）。
不做任何 LLM 调用 —— 最后一题提交后由 /api/submit_answer 触发异步任务生成，
前端轮询 /api/task_status/{summary_task_id} 拿到，总结页秒开。
"""


def _rows_as_dicts(cur) -> list:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def build_summary(pg_conn, user_id: int, question_ids: list) -> dict:
    """按题目 ID 列表聚合本次会话：正确率 / 用时 / 每知识点 Elo 变化 / 错题回顾"""
    qids = [int(x) for x in (question_ids or [])]
    if not qids:
        return {"total": 0, "correct": 0, "wrong": 0, "accuracy": 0,
                "duration_sec": 0, "kps": [], "weak_names": [],
                "wrong_questions": []}

    with pg_conn.cursor() as cur:
        # 每题只取最近一次作答（同一题重复提交也以最后一次为准）
        cur.execute("""
            WITH latest AS (
                SELECT DISTINCT ON (question_id)
                       question_id, user_answer, is_correct, duration_sec,
                       elo_delta, theta_before, created_at
                FROM quiz_records
                WHERE user_id=%s AND question_id = ANY(%s)
                ORDER BY question_id, created_at DESC, id DESC
            )
            SELECT q.id, q.knowledge_point_id, q.qtype, q.stem, q.options,
                   q.answer, q.analysis, kp.name AS kp_name,
                   l.user_answer, l.is_correct, l.duration_sec,
                   l.elo_delta, l.theta_before
            FROM latest l
            JOIN questions q ON q.id = l.question_id
            JOIN knowledge_points kp ON kp.id = q.knowledge_point_id
            ORDER BY l.created_at, l.question_id
        """, (user_id, qids))
        rows = _rows_as_dicts(cur)

        # 各知识点当前掌握度（theta_after 以 mastery_states 为准）
        kp_ids = sorted({r["knowledge_point_id"] for r in rows})
        if kp_ids:
            cur.execute("""SELECT knowledge_point_id, elo_theta
                           FROM mastery_states
                           WHERE user_id=%s AND knowledge_point_id = ANY(%s)""",
                        (user_id, kp_ids))
            theta_now = {k: float(v) for k, v in cur.fetchall()}
        else:
            theta_now = {}

    total = len(rows)
    correct = sum(1 for r in rows if r["is_correct"])
    duration = sum(r["duration_sec"] or 0 for r in rows)

    kp_map: dict = {}
    for r in rows:
        k = kp_map.setdefault(r["knowledge_point_id"], {
            "kp_id": r["knowledge_point_id"], "name": r["kp_name"],
            "correct": 0, "wrong": 0, "theta_before": None, "theta_after": None,
        })
        if r["is_correct"]:
            k["correct"] += 1
        else:
            k["wrong"] += 1
        # 会话起点 = 该知识点第一次作答前的掌握度快照
        if k["theta_before"] is None and r["theta_before"] is not None:
            k["theta_before"] = round(float(r["theta_before"]), 1)

    for k in kp_map.values():
        t = theta_now.get(k["kp_id"])
        k["theta_after"] = round(t, 1) if t is not None else k["theta_before"]

    wrong_questions = [
        {"stem": r["stem"], "kp_name": r["kp_name"],
         "user_answer": r["user_answer"] or "（未作答）",
         "correct_answer": r["answer"], "analysis": r["analysis"]}
        for r in rows if not r["is_correct"]
    ]
    weak_names = [k["name"] for k in kp_map.values() if k["wrong"] > 0]

    return {
        "total": total,
        "correct": correct,
        "wrong": total - correct,
        "accuracy": round(correct * 100 / total) if total else 0,
        "duration_sec": duration,
        "kps": list(kp_map.values()),
        "weak_names": weak_names,
        "wrong_questions": wrong_questions,
    }
