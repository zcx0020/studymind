"""03_demo_adaptive.py —— M6 创新点演示：答错 → 诊断 → 计划动态调整 → 难度自适应出题
前置: 已运行 02_demo_no_pdf.py（复用其知识库与学习计划）
用法: cd studymind && python3 scripts/03_demo_adaptive.py
"""
import os
import sys
from pathlib import Path

# 国内环境从 hf-mirror 下载 huggingface 模型（BGE-M3 约 2.3GB）；能直连则不受影响
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import chromadb
import psycopg2
from neo4j import GraphDatabase

from app.config import settings
from app.services.llm import get_embedder
from app.services.diagnostic.engine import on_wrong_answer, on_mastered
from app.services.quiz.generate import build_today_quiz, fetch_question_full
from app.services.quiz.mastery import record_and_update
from app.services.rag.adaptive_quiz import AdaptiveQuizService, ChromaRetriever


def main():
    pg = psycopg2.connect(settings.pg_dsn)
    neo = GraphDatabase.driver(settings.neo4j_uri,
                               auth=(settings.neo4j_user, settings.neo4j_password))
    embedder = get_embedder()
    chroma = chromadb.PersistentClient(path=settings.chroma_path)

    # 找 02 创建的最新知识库与计划
    with pg.cursor() as cur:
        cur.execute("""SELECT id FROM documents
                       WHERE source_type='llm_generated' ORDER BY id DESC LIMIT 1""")
        doc_id = cur.fetchone()[0]
        cur.execute("""SELECT id FROM study_plans
                       WHERE document_id=%s ORDER BY id DESC LIMIT 1""", (doc_id,))
        plan_id = cur.fetchone()[0]

    retriever = ChromaRetriever(chroma, f"doc_{doc_id}", embedder)
    service = AdaptiveQuizService(retriever)
    quiz = build_today_quiz(pg, plan_id, 1, service)

    target = quiz["items"][0]
    kp_id = target["kp_id"]
    print(f"选定薄弱点模拟: {target['name']} (θ={target['theta']})")
    full = fetch_question_full(pg, target["questions"][0]["id"])
    print(f"初始题目: 难度{full['difficulty']} 层次{full['bloom']} | {full['stem'][:40]}...")

    # ① 连续答错 2 次 → 触发动态调整引擎（生产环境中由答题接口异步触发）
    for _ in range(2):
        record_and_update(pg, 1, full, "错误的回答", False)
    print("\n[触发] 连续答错 → 动态调整引擎启动...")

    # ② GraphRAG 诊断 + 计划重排
    result = on_wrong_answer(pg, neo, 1, kp_id)
    print(f"[诊断] 根因: {result['root_cause']}")
    print(f"[诊断] 补学路径: {' → '.join(result['remedy_path'])}")
    print(f"[诊断] 出题策略: {result['next_strategy']}")
    print(f"[诊断] 易混淆概念: {result['confused_concepts']}")
    print(f"[计划] 调整项 ({len(result['changes'])} 条):")
    for c in result["changes"]:
        if c["action"] == "move_earlier":
            print(f"   - {c['action']}: {c['kp']} 从Day{c['from_day']}提前到Day{c['to_day']}")
        else:
            print(f"   - {c['action']}: {c['kp']} → Day{c['day']}")

    # ③ 重新获取今日任务 → 新题目应按诊断策略降难度（自适应出题生效）
    quiz2 = build_today_quiz(pg, plan_id, 1, service)
    print("\n[自适应出题] 调整后的今日题目:")
    for item in quiz2["items"]:
        for qq in item["questions"]:
            f = fetch_question_full(pg, qq["id"])
            mark = "★" if f["knowledge_point_id"] == kp_id else " "
            print(f"   {mark} {item['name']}: 难度{f['difficulty']} 层次{f['bloom']}")

    # ④ 掌握机制：连对 3 题 → 计划中该知识点任务自动跳过
    for _ in range(3):
        record_and_update(pg, 1, full, full["answer"], True)
    skipped = on_mastered(pg, 1, kp_id)
    print(f"\n[掌握] 连对3题 → 计划中 {skipped['skipped']} 条任务标记完成(跳过)")

    print("\n✅ 动态调整闭环演示完成: 答错→诊断→计划重排→降难度→再练→掌握→跳过")


if __name__ == "__main__":
    main()
