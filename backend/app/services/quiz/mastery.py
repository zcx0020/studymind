"""quiz/mastery.py —— 掌握度状态机（Elo）与落库
P(答对)=1/(1+10^(-(θ-β)/400))；答对 θ+=K(1-P)，答错 θ-=K·P
连续答对≥3 或 θ≥1700 判定"已掌握"，供动态调整引擎消费
"""
import json

from app.config import settings
from app.services.rag.adaptive_quiz import difficulty_to_elo, elo_update


def get_theta(pg_conn, user_id: int, kp_id: int) -> float:
    with pg_conn.cursor() as cur:
        cur.execute("""SELECT elo_theta FROM mastery_states
                       WHERE user_id=%s AND knowledge_point_id=%s""",
                    (user_id, kp_id))
        row = cur.fetchone()
    return float(row[0]) if row else settings.elo_initial


def record_and_update(pg_conn, user_id: int, q: dict, user_answer: str,
                      is_correct: bool, grading=None,
                      duration_sec: int | None = None) -> dict:
    """答题记录落库 + mastery_states 原子更新，返回最新掌握度状态。
    quiz_records 同时写入 elo_delta / theta_before 快照，供会话总结聚合"""
    with pg_conn.cursor() as cur:
        # ② 读当前状态（行锁，防并发丢更新）
        cur.execute("""SELECT elo_theta, streak FROM mastery_states
                       WHERE user_id=%s AND knowledge_point_id=%s
                       FOR UPDATE""", (user_id, q["knowledge_point_id"]))
        row = cur.fetchone()
        theta = float(row[0]) if row else settings.elo_initial
        new_streak = (row[1] + 1) if (row and is_correct) else (1 if is_correct else 0)
        new_theta = elo_update(theta, difficulty_to_elo(float(q["difficulty"])),
                               is_correct, settings.elo_k)
        delta = new_theta - theta
        # ① 答题记录（诊断引擎与总结的数据来源，含 Elo 快照）
        cur.execute("""INSERT INTO quiz_records
                       (user_id, question_id, is_correct, user_answer, llm_feedback,
                        duration_sec, elo_delta, theta_before)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (user_id, q["id"], is_correct, user_answer,
                     json.dumps(grading.model_dump(), ensure_ascii=False)
                     if grading else None,
                     duration_sec, delta, theta))
        # ③ upsert（唯一约束 + ON CONFLICT 原子累加）
        cur.execute("""INSERT INTO mastery_states
                       (user_id, knowledge_point_id, elo_theta,
                        correct_count, wrong_count, streak, last_review_at)
                       VALUES (%s,%s,%s,%s,%s,%s,now())
                       ON CONFLICT (user_id, knowledge_point_id) DO UPDATE SET
                         elo_theta      = EXCLUDED.elo_theta,
                         streak         = EXCLUDED.streak,
                         correct_count  = mastery_states.correct_count  + EXCLUDED.correct_count,
                         wrong_count    = mastery_states.wrong_count    + EXCLUDED.wrong_count,
                         last_review_at = now(), updated_at = now()""",
                    (user_id, q["knowledge_point_id"], new_theta,
                     1 if is_correct else 0, 0 if is_correct else 1, new_streak))
        pg_conn.commit()
    return {"theta": round(new_theta, 1), "theta_before": round(theta, 1),
            "delta": round(delta, 1), "streak": new_streak,
            "mastered": new_streak >= settings.mastered_streak
                        or new_theta >= settings.elo_mastered}
