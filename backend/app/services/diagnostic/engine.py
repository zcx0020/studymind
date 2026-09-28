"""diagnostic/engine.py —— 动态调整引擎（M6，创新点核心）

触发链（生产环境在答题接口中由 Celery 异步调用，demo 直接调用）:
  答题判分(is_correct=False) ──► on_wrong_answer() ──► 诊断落库 + 计划重排
  答题判分(state['mastered']) ──► on_mastered()    ──► 计划跳过已掌握任务
再出题时 quiz/generate.py 读取最新诊断报告 → AdaptiveQuizService 按其策略
调整难度/认知层次/干扰项，形成"答错→诊断→重排→降难度→再练→掌握"闭环
"""
import json
import re

from app.services.rag.adaptive_quiz import run_diagnosis


def _get_active_plan(pg_conn, user_id: int, doc_id: int):
    with pg_conn.cursor() as cur:
        cur.execute("""SELECT id FROM study_plans
                       WHERE user_id=%s AND document_id=%s AND status='active'
                       ORDER BY id DESC LIMIT 1""", (user_id, doc_id))
        row = cur.fetchone()
    return row[0] if row else None


def _get_theta_map(pg_conn, user_id: int) -> dict:
    """全部知识点掌握度 {name: theta}，诊断时注入图谱邻域"""
    with pg_conn.cursor() as cur:
        cur.execute("""SELECT kp.name, m.elo_theta
                       FROM mastery_states m
                       JOIN knowledge_points kp ON kp.id = m.knowledge_point_id
                       WHERE m.user_id=%s""", (user_id,))
        return {name: float(theta) for name, theta in cur.fetchall()}


def _kp_id_by_name(pg_conn, doc_id: int, name: str):
    with pg_conn.cursor() as cur:
        cur.execute("""SELECT id FROM knowledge_points
                       WHERE document_id=%s AND name=%s""", (doc_id, name))
        row = cur.fetchone()
    return row[0] if row else None


def _resolve_kp(pg_conn, doc_id: int, entry: str):
    """把诊断输出的补学条目解析为教材中的知识点ID。
    兼容: 精确名称 / "名称：解释"前缀 / 名称作为子串出现（LLM 输出格式漂移的兜底）
    """
    direct = _kp_id_by_name(pg_conn, doc_id, entry)
    if direct:
        return direct
    head = entry.split("：")[0].split(":")[0].strip()
    head_id = _kp_id_by_name(pg_conn, doc_id, head)
    if head_id:
        return head_id
    with pg_conn.cursor() as cur:
        cur.execute("SELECT name FROM knowledge_points WHERE document_id=%s", (doc_id,))
        for (name,) in cur.fetchall():
            if name in entry:
                return _kp_id_by_name(pg_conn, doc_id, name)
    return None


def _current_day(pg_conn, plan_id: int, kp_id: int) -> int:
    """薄弱点所在计划日；不在计划中则用最早 pending 日"""
    with pg_conn.cursor() as cur:
        cur.execute("""SELECT day_index FROM plan_items
                       WHERE plan_id=%s AND knowledge_point_id=%s AND status='pending'
                       ORDER BY day_index LIMIT 1""", (plan_id, kp_id))
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute("""SELECT MIN(day_index) FROM plan_items
                       WHERE plan_id=%s AND status='pending'""", (plan_id,))
        row = cur.fetchone()
    return row[0] if row and row[0] else 1


def _first_free_day(pg_conn, plan_id: int, start_day: int, max_per_day: int = 5) -> int:
    """从 start_day 起找第一个 pending 任务数 < max_per_day 的日子。
    自适应插入不再堆爆某一天（每天上限 5 个，与计划生成口径一致）"""
    with pg_conn.cursor() as cur:
        cur.execute("""SELECT day_index, COUNT(*) FROM plan_items
                       WHERE plan_id=%s AND status='pending'
                       GROUP BY day_index""", (plan_id,))
        counts = dict(cur.fetchall())
    d = start_day
    while counts.get(d, 0) >= max_per_day:
        d += 1
    return d


def apply_diagnosis(pg_conn, user_id: int, weak_kp_id: int, diag) -> dict:
    """把诊断结论落到学习计划上。所有改动记为 changes，供前端提示"计划已调整"。

    规则:
    - 补学路径中的前置知识点: 不在计划 → 插入 learn 任务(当前日); 排在后面 → 提前到当前日
    - 易混淆概念: 插入 review 对比任务(当前日)，幂等防重复
    """
    changes = []
    with pg_conn.cursor() as cur:
        cur.execute("SELECT name, document_id FROM knowledge_points WHERE id=%s",
                    (weak_kp_id,))
        kp_name, doc_id = cur.fetchone()
    plan_id = _get_active_plan(pg_conn, user_id, doc_id)
    if plan_id is None:
        return {"plan_id": None, "changes": changes, "note": "无活跃计划，跳过重排"}

    day = _current_day(pg_conn, plan_id, weak_kp_id)
    insert_day = _first_free_day(pg_conn, plan_id, day)   # 均衡插入：当天满 5 个自动顺延

    # ① 补学路径：前置知识点插入 / 提前到最早有空位的日子
    for name in diag.remedy_path:
        if name == kp_name:
            continue
        kid = _resolve_kp(pg_conn, doc_id, name)
        if kid is None:                        # 诊断提到的知识点不在本教材 → 跳过
            continue
        with pg_conn.cursor() as cur:
            cur.execute("""SELECT id, day_index, status FROM plan_items
                           WHERE plan_id=%s AND knowledge_point_id=%s
                           ORDER BY day_index DESC LIMIT 1""", (plan_id, kid))
            row = cur.fetchone()
        if row is None:
            with pg_conn.cursor() as cur:
                cur.execute("""INSERT INTO plan_items
                               (plan_id, knowledge_point_id, day_index, task_type,
                                est_minutes, status, created_by)
                               VALUES (%s,%s,%s,'learn',15,'pending','adaptive')""",
                            (plan_id, kid, insert_day))
                pg_conn.commit()
            changes.append({"action": "insert_learn", "kp": name, "day": insert_day})
        elif row[2] == "pending" and row[1] > day:
            target = _first_free_day(pg_conn, plan_id, 1)
            if target < row[1]:
                with pg_conn.cursor() as cur:
                    cur.execute("""UPDATE plan_items SET day_index=%s, created_by='adaptive'
                                   WHERE id=%s""", (target, row[0]))
                    pg_conn.commit()
                changes.append({"action": "move_earlier", "kp": name,
                                "from_day": row[1], "to_day": target})
        # done(已学过) 或已排在当前日之前 → 不动

    # ② 概念混淆：插入对比复习任务（幂等：已有同类 pending 任务则不重复插入）
    #    诊断输出形如 "A vs B（说明）"，拆出两侧名称分别解析
    for entry in diag.confused_concepts:
        sides = re.split(r"\s*(?:vs|VS|与|和)\s*", entry.split("（")[0].split("(")[0])
        for side in sides:
            kid = _resolve_kp(pg_conn, doc_id, side.strip())
            if kid is None or kid == weak_kp_id:
                continue
            with pg_conn.cursor() as cur:
                cur.execute("""SELECT 1 FROM plan_items
                               WHERE plan_id=%s AND knowledge_point_id=%s
                                 AND task_type='review' AND status='pending'""",
                            (plan_id, kid))
                exists = cur.fetchone()
            if not exists:
                review_day = _first_free_day(pg_conn, plan_id, insert_day)
                with pg_conn.cursor() as cur:
                    cur.execute("""INSERT INTO plan_items
                                   (plan_id, knowledge_point_id, day_index, task_type,
                                    est_minutes, status, created_by)
                                   VALUES (%s,%s,%s,'review',10,'pending','adaptive')""",
                                (plan_id, kid, review_day))
                    pg_conn.commit()
                changes.append({"action": "insert_review", "kp": side.strip(),
                                "day": review_day})

    return {"plan_id": plan_id, "weak_kp": kp_name, "day": day, "changes": changes}


def on_wrong_answer(pg_conn, driver, user_id: int, weak_kp_id: int) -> dict:
    """答错后的完整调整链：GraphRAG 诊断 → 报告落库 → 计划重排"""
    with pg_conn.cursor() as cur:
        cur.execute("SELECT name FROM knowledge_points WHERE id=%s", (weak_kp_id,))
        kp_name = cur.fetchone()[0]

    theta_map = _get_theta_map(pg_conn, user_id)
    diag = run_diagnosis(user_id, kp_name, theta_map, driver, pg_conn)

    with pg_conn.cursor() as cur:
        cur.execute("""INSERT INTO diagnosis_reports
                       (user_id, weak_kp_id, root_cause, remedy_path,
                        next_strategy, confused_concepts)
                       VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
                    (user_id, weak_kp_id, diag.root_cause,
                     json.dumps(diag.remedy_path, ensure_ascii=False),
                     json.dumps(diag.next_strategy, ensure_ascii=False),
                     json.dumps(diag.confused_concepts, ensure_ascii=False)))
        report_id = cur.fetchone()[0]
        pg_conn.commit()

    plan_result = apply_diagnosis(pg_conn, user_id, weak_kp_id, diag)
    return {"report_id": report_id, "root_cause": diag.root_cause,
            "remedy_path": diag.remedy_path, "next_strategy": diag.next_strategy,
            "confused_concepts": diag.confused_concepts, **plan_result}


def on_mastered(pg_conn, user_id: int, kp_id: int) -> dict:
    """连续答对达标 → 计划中该知识点的 pending 任务全部标记完成（跳过机制）"""
    with pg_conn.cursor() as cur:
        cur.execute("""SELECT p.id AS plan_id FROM study_plans p
                       JOIN knowledge_points kp ON kp.document_id = p.document_id
                       WHERE p.user_id=%s AND kp.id=%s AND p.status='active'
                       ORDER BY p.id DESC LIMIT 1""", (user_id, kp_id))
        row = cur.fetchone()
        if row is None:
            return {"skipped": 0, "note": "无活跃计划"}
        cur.execute("""UPDATE plan_items SET status='done', created_by='adaptive'
                       WHERE plan_id=%s AND knowledge_point_id=%s AND status='pending'""",
                    (row[0], kp_id))
        skipped = cur.rowcount
        pg_conn.commit()
    return {"plan_id": row[0], "skipped": skipped}
