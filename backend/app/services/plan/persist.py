"""plan/persist.py —— 计划与条目入库（study_plans / plan_items）"""


def save_plan(pg_conn, user_id: int, plan_data: dict) -> int:
    with pg_conn.cursor() as cur:
        cur.execute("""INSERT INTO study_plans (user_id, document_id, goal, total_days, daily_limit)
                       VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                    (user_id, plan_data["doc_id"], plan_data.get("goal_text", ""),
                     plan_data["total_days"], plan_data.get("daily_limit", 5)))
        plan_id = cur.fetchone()[0]

        # name → kp_id 映射
        cur.execute("SELECT id, name FROM knowledge_points WHERE document_id=%s",
                    (plan_data["doc_id"],))
        kp_ids = {name: kpid for kpid, name in cur.fetchall()}

        for day in range(1, plan_data["total_days"] + 1):
            for name in plan_data["days"][day]:
                it = plan_data["items"][name]
                cur.execute("""INSERT INTO plan_items
                               (plan_id, knowledge_point_id, day_index,
                                task_type, est_minutes, status, created_by)
                               VALUES (%s,%s,%s,%s,%s,'pending','llm')""",
                            (plan_id, kp_ids[name], day,
                             it["task_type"], it["est_minutes"]))
        pg_conn.commit()
    return plan_id
