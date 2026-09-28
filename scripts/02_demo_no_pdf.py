"""02_demo_no_pdf.py —— 无教材模式端到端演示（M1~M5 垂直切片）
前置:
  1. docker compose up -d   （PostgreSQL + Neo4j + Redis，首次启动自动建表）
  2. pip install -r requirements.txt
  3. python3 scripts/01_smoke_test.py 通过
用法: cd studymind && python3 scripts/02_demo_no_pdf.py
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
from app.services.knowledge.skeleton import generate_skeleton
from app.services.knowledge.persist import persist_skeleton
from app.services.plan.generate import generate_plan
from app.services.plan.persist import save_plan
from app.services.quiz.generate import build_today_quiz, fetch_question_full
from app.services.quiz.mastery import record_and_update
from app.services.rag.adaptive_quiz import AdaptiveQuizService, ChromaRetriever


def main():
    pg = psycopg2.connect(settings.pg_dsn)
    neo = GraphDatabase.driver(settings.neo4j_uri,
                               auth=(settings.neo4j_user, settings.neo4j_password))
    embedder = get_embedder()
    chroma = chromadb.PersistentClient(path=settings.chroma_path)

    # ① 主题 → 知识骨架 → 三库入库
    print("① 生成知识骨架（DeepSeek）...")
    sk = generate_skeleton("机器学习", "线性回归")
    stats = persist_skeleton(1, "机器学习", "线性回归", sk, pg, neo, embedder, chroma)
    print(f"   入库完成: {stats['entities']} 个知识点, {stats['relations']} 条关系 "
          f"(doc_id={stats['doc_id']})")

    # ② 图谱 → 学习计划
    print("② 生成学习计划...")
    plan = generate_plan(1, stats["doc_id"], neo, pg, 7, 45,
                         "两周内掌握该主题", "机器学习", "线性回归")
    if plan["leftovers"]:
        print(f"   ⚠ 图谱存在环({plan['leftovers']})，已降级处理为同天学习")
    plan_id = save_plan(pg, 1, plan)
    print(f"   计划已生成 (plan_id={plan_id})")
    print(f"   Day1: {'、'.join(plan['days'][1])}")
    print(f"   Day1 目标: {plan['enrich'][1].goal}")

    # ③ 今日任务出题
    print("③ 生成今日任务题目...")
    retriever = ChromaRetriever(chroma, f"doc_{stats['doc_id']}", embedder)
    service = AdaptiveQuizService(retriever)
    quiz = build_today_quiz(pg, plan_id, 1, service)
    for item in quiz["items"]:
        print(f"   {item['name']}: {len(item['questions'])} 题 "
              f"(θ={item['theta']})  -- {item['questions'][0]['stem'][:40]}...")

    # ④ 模拟答题（答对 → Elo 上升；答错 → 下降）
    print("④ 模拟答题...")
    first_q = quiz["items"][0]["questions"][0]
    full = fetch_question_full(pg, first_q["id"])
    s1 = record_and_update(pg, 1, full, full["answer"], True)
    print(f"   第1题答对 → θ={s1['theta']} 连对{s1['streak']}")
    s2 = record_and_update(pg, 1, full, "完全错误的回答", False)
    print(f"   同题再答错 → θ={s2['theta']} 连对{s2['streak']}")

    print("\n✅ 端到端演示完成：知识库 → 学习计划 → 今日题目 → 答题 → 掌握度更新")
    print("   查看图谱: http://localhost:7474 执行 MATCH (n)-[r]->(m) RETURN n,r,m LIMIT 50")


if __name__ == "__main__":
    main()
