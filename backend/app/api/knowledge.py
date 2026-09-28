"""api/knowledge.py —— 无教材知识库生成 + 知识图谱数据接口"""
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api import deps
from app.services import taskman
from app.services.knowledge.skeleton import generate_skeleton
from app.services.knowledge.persist import persist_skeleton
from app.services.llm import get_embedder

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


class GenerateRequest(BaseModel):
    subject: str = Field(description="科目，如 机器学习")
    topic: str = Field(description="主题，如 线性回归")
    user_id: int = 1
    min_entities: int = 12
    max_entities: int = 25


@router.post("/generate")
def generate(req: GenerateRequest):
    """选主题生成知识库。异步任务：轮询 /api/tasks/{task_id} 拿进度与结果"""
    t = taskman.run_task("knowledge_generate", _build_kb, req)
    return {"task_id": t.id}


def _build_kb(t: taskman.TaskState, req: GenerateRequest) -> dict:
    t.stage = "LLM 生成知识骨架中"
    t.progress = 10
    sk = generate_skeleton(req.subject, req.topic, req.min_entities, req.max_entities)
    t.stage = "写入 PostgreSQL / Neo4j / Chroma"
    t.progress = 50
    pg = deps.new_pg()
    try:
        stats = persist_skeleton(req.user_id, req.subject, req.topic, sk,
                                 pg, deps.get_neo4j(), get_embedder(), deps.get_chroma())
    finally:
        pg.close()
    return {"doc_id": stats["doc_id"], "entities": stats["entities"],
            "relations": stats["relations"]}


@router.get("/graph/{doc_id}")
def graph(doc_id: int):
    """知识图谱数据（前端 G6 渲染）：节点 + 边"""
    driver = deps.get_neo4j()
    nodes, _, _ = driver.execute_query(
        """MATCH (n) WHERE n.doc_id = $doc
           RETURN n.name AS name, labels(n)[0] AS type,
                  COALESCE(n.importance, 3) AS importance,
                  COALESCE(n.difficulty, 3) AS difficulty,
                  COALESCE(n.definition, '') AS definition""", doc=doc_id)
    edges, _, _ = driver.execute_query(
        """MATCH (a)-[r]->(b)
           WHERE a.doc_id = $doc AND b.doc_id = $doc
           RETURN a.name AS source, b.name AS target, type(r) AS type""", doc=doc_id)
    # neo4j Record 转 dict（否则 JSON 序列化成值列表，前端无法按字段名取数）
    return {"nodes": [dict(n) for n in nodes], "edges": [dict(e) for e in edges]}
