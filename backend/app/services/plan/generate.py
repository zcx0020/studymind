"""plan/generate.py —— 图谱拉取 + 算法分配 + LLM润色 = 结构化学习计划
双引擎：算法保证"先学什么后学什么"合法且容量合理；LLM 负责教学文案
"""
import math
from typing import Dict, List

from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate

from app.config import settings
from app.services.llm import get_structured_llm
from .topo import topological_layers, pack_days


# ── ① LLM 润色输出契约 ──
class DayEnrichment(BaseModel):
    day_index: int = Field(description="第几天，与输入顺序一致")
    goal: str = Field(description="当天学习目标，一句话，具体可执行")
    focus_points: List[str] = Field(description="2~3条学习重点提示，必须基于当天知识点")
    quiz_hint: str = Field(description="当天练习侧重建议")


class PlanEnrichment(BaseModel):
    days: List[DayEnrichment]


# ── ② 润色 Prompt（分配表由算法给出，LLM 不得改动） ──
ENRICH_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """你是大学课程学习规划师。给定一份"知识点按天分配表"（分配已由算法按前置依赖排好，不得改动），为每一天撰写教学文案。

## 要求
1. goal：一句话说清当天学完应达到的程度
2. focus_points：2~3条，基于当天知识点内容，指出易错点或理解难点
3. quiz_hint：建议当天练习侧重哪个知识点/题型
4. days 数组必须覆盖输入的每一天，顺序一致，不得增删调换知识点"""),
    ("human", """科目: {subject}  主题: {topic}
总体目标: {goal_text}  共 {total_days} 天，每天约 {minutes_per_day} 分钟

## 知识点按天分配表
{day_table}"""),
])


# ── ③ 图谱拉取 ──
def fetch_course_graph(driver, doc_id: int):
    nodes, _, _ = driver.execute_query(
        """MATCH (n) WHERE n.doc_id = $doc
           RETURN n.name AS name, labels(n)[0] AS type,
                  COALESCE(n.importance, 3) AS importance,
                  COALESCE(n.difficulty, 3) AS difficulty""", doc=doc_id)
    edges, _, _ = driver.execute_query(
        """MATCH (a)-[r:PREREQUISITE_OF]->(b)
           WHERE a.doc_id = $doc AND b.doc_id = $doc
           RETURN a.name AS pre, b.name AS post""", doc=doc_id)
    return list(nodes), [(e["pre"], e["post"]) for e in edges]


# ── ④ 主流程 ──
def generate_plan(user_id: int, doc_id: int, driver, pg_conn,
                  total_days: int, minutes_per_day: int,
                  goal_text: str, subject: str, topic: str,
                  daily_limit: int = 5) -> dict:
    # ① 拉图
    nodes, edges = fetch_course_graph(driver, doc_id)
    names = [n["name"] for n in nodes]
    kp_info = {n["name"]: (n["importance"], n["difficulty"]) for n in nodes}
    prereq_map: Dict[str, List[str]] = {n: [] for n in names}
    for pre, post in edges:
        prereq_map[post].append(pre)

    # ② 自动延期：每天上限 = 用户自定义 daily_limit 个知识点、
    #    分钟预算 = max(请求值, daily_limit×12)（保证每天装得下），
    #    容量不够就加天数，绝不堆最后一天。延期计算与装箱必须用同一预算口径！
    daily_limit = max(1, min(daily_limit, 20))
    day_budget = max(minutes_per_day, daily_limit * 12)
    est_total = sum(min(8 + kp_info[n][1] * 3, 12) for n in names)
    needed_days = max(
        total_days,
        math.ceil(len(names) / daily_limit),
        math.ceil(est_total / day_budget),
    )
    extended = needed_days > total_days

    # ③ 拓扑分层 + 装箱（确定性分配，前置先学；天数与预算都用上面计算好的值）
    priority = {n["name"]: n["importance"] for n in nodes}
    layers, leftovers = topological_layers(names, edges, priority)
    kp_day = pack_days(layers, prereq_map, kp_info, needed_days, day_budget,
                       max_per_day=daily_limit)

    # ④ 掌握度介入：θ 达到阈值视为已掌握 → 降级为复习任务（时长减半）
    with pg_conn.cursor() as cur:
        cur.execute("""SELECT kp.name, m.elo_theta FROM mastery_states m
                       JOIN knowledge_points kp ON kp.id = m.knowledge_point_id
                       WHERE m.user_id=%s AND kp.document_id=%s""",
                    (user_id, doc_id))
        mastered = {name for name, theta in cur.fetchall()
                    if theta >= settings.elo_mastered}

    # ⑤ 组每日清单（空白天补复习任务）
    items = {n: {"day": kp_day[n],
                 "task_type": "review" if n in mastered else "learn",
                 "est_minutes": max(5, min(8 + kp_info[n][1] * 3, 12)
                                    // (2 if n in mastered else 1))}
             for n in names}
    by_day: Dict[int, List[str]] = {d: [] for d in range(1, needed_days + 1)}
    for n, it in items.items():
        by_day[it["day"]].append(n)
    top_kps = sorted(names, key=lambda n: -kp_info[n][0])
    for d in range(1, needed_days + 1):
        if not by_day[d]:
            by_day[d] = top_kps[:2]

    # ⑥ 组分配表文本 → LLM 润色（自愈重试保证天数全覆盖）
    day_table = "\n".join(
        f"Day{d}: " + "、".join(
            f"{n}(前置:{'/'.join(prereq_map[n]) if prereq_map[n] else '无'})"
            for n in by_day[d])
        for d in by_day)
    llm = get_structured_llm(PlanEnrichment, temperature=0.3)
    for _ in range(3):
        enrich: PlanEnrichment = llm.invoke(ENRICH_PROMPT.format(
            subject=subject, topic=topic, goal_text=goal_text,
            total_days=needed_days, minutes_per_day=minutes_per_day,
            day_table=day_table))
        if {d.day_index for d in enrich.days} == set(range(1, needed_days + 1)):
            break
    else:
        raise RuntimeError("润色结果天数覆盖校验连续失败")

    return {"doc_id": doc_id, "days": by_day, "items": items,
            "enrich": {d.day_index: d for d in enrich.days},
            "layers": layers, "leftovers": leftovers,
            "total_days": needed_days, "requested_days": total_days,
            "extended": extended, "daily_limit": daily_limit,
            "goal_text": goal_text}
